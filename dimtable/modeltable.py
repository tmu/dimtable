# ---------------------------------------------------------------------------
# modeltable
# ---------------------------------------------------------------------------

import logging
import json

from django.utils.safestring import mark_safe
from django.core import exceptions
import django.db.models.fields.related
from django.forms.widgets import TextInput
import django.db.models.fields

import html
import dimtable
import ddict
from dimtable import Dim

logger = logging.getLogger('dimtable')

# ---------------------------------------------------------------------------
# Implementation notes
# 
# String concatenations in this module should be at least somewhat optimized as
# with large tables there are a lot of them. Avoid s1 + s2 + s3 ... style.
# Apparently, "".join(xs) is normally the fastest method.
# http://stackoverflow.com/questions/1316887/what-is-the-most-efficient-string-concatenation-method-in-python

def get_model_field(model, fieldname):
    return model._meta.get_field_by_name(fieldname)[0]

def ndigits(i):
    return len(str(i))

def write_list(xs):
    return ",".join(xs)

def read_list(s):
    return s.split(',') 

def parse_value(valstr, field):
    value = None
    error = None
    try:
        if valstr or field.empty_strings_allowed:
            value = field.to_python(valstr)
    except exceptions.ValidationError, e:
        error = e
    return value, error


class CellError:
    def __init__(self, err, cellix, inputted_value):
        self.err = err
        self.cellix = cellix
        self.inputted_value = inputted_value

    def messages(self):
        if hasattr(self.err, 'messages'):
            msgs = self.err.messages
            if type(msgs) == dict:
                return msgs.values()
            else:
                return msgs
        else:
            return [unicode(self.err)]

# ----------------------------------------------------------------------
# modeltable ValueItem
# ----------------------------------------------------------------------

class ValueItem(dimtable.LabelItem):
    def __init__(self, model, fieldname, value, renderer = unicode):
        dimtable.LabelItem.__init__(self, value, renderer)
        self.model      = model
        self.fieldname = fieldname

    def matches_instance(self, instance):
        fieldvalue = getattr(instance, self.fieldname)
        return fieldvalue == self.value()

    def get_field(self):
        return get_model_field(self.model, self.fieldname)

    def hidden_serialize(self):
        field = self.get_field()
        v = self.value()
        if isinstance(field,   django.db.models.fields.related.ForeignKey):
            return str(v.id)
        elif isinstance(field, django.db.models.fields.DateField):
            return v.strftime('%Y%m%d')
        else:
            return str(v)

    def editable(self): return True

def valueitems(model, fieldname, values, renderer = unicode):
    return [ValueItem(model, fieldname, v, renderer) for v in values]

# ----------------------------------------------------------------------
# modeltable InputItem
# ----------------------------------------------------------------------
class InputItem(dimtable.LabelItem):
    def __init__(self, model, fieldname, renderer=None):
        if renderer is None:
            renderer = self.show_verbose_name
        dimtable.LabelItem.__init__(self, fieldname, renderer)
        self.model = model
        self.fieldname = fieldname

    def show_verbose_name(self, fieldname):
        return self.get_field().verbose_name

    def get_field(self):
        return get_model_field(self.model, self.fieldname)

    def editable(self): return True

    def render_instance(self, inst, cellindex):
        if inst is None: return u''

        fieldvalue = getattr(inst, self.fieldname)
        field = self.get_field()

        if isinstance(field, django.db.models.fields.DecimalField):
            format = u"%." + unicode(field.decimal_places) + "f"
            return format % fieldvalue
        else:
            return unicode(fieldvalue)

class CustomItem(dimtable.LabelItem):
    def __init__(self, name):
        dimtable.LabelItem.__init__(self, name)
        
    def editable(self): return False
    def render_instance(self, inst, cellindex):
        return u'n/a'
    

# ----------------------------------------------------------------------
# modeltable Dim 
# ----------------------------------------------------------------------

class InputDim(dimtable.Dim):
    def __init__(self, items): 
        dimtable.Dim.__init__(self, items)

# ----------------------------------------------------------------------
# Data. 
# Modeltables are used to show and edit instances of a single Django model.
# How fields of the Django model maps to table is described by Data:
# - fields that are row dimensions
# - fields that are column dimensions
# - field that is represented by cells
# 
# If you want to use different data structures for instance lookups 
# or do some custom saving behavior, you can create a similar class,
# with following methods
#
#    def save(self, cellix, instance_id, value):
# 
#    def get(self, cellindex)
#         # return instance for cellindex
#
#    def create_instance(self, cellix, value) 
#         # create and save a new instance to database
#
#    def delete_instance(self, cellix, instance_id)
#         # delete an instance from database 
#
#    def update_instance(self, cellix, instance_id, value)
#         # update an existing instance 
#
# Data doesn't describe how cells and dimensions are represented,
# how errors of edited cells are stored and shown, etc.
# Those representational aspects are left for modeltable.Presenter
#
#
# 
# ----------------------------------------------------------------------

class Data(object):
    def __init__(self, model, inputdim, instances, rowdims, coldims, **kwargs):
        self.model        = model
        self.inputdim     = inputdim
        if self.is_single_input(): self.rowdims      = rowdims
        else:                      self.rowdims      = rowdims + [inputdim]

        self.coldims      = coldims
        self.fixed_fields = kwargs.get('fixed_fields', [])

        # instdict is an internal data structure 
        # for fast instance lookups by cell index
        self.instdict     = {} 

        self._create_instdict(instances, 
                              self.valuerange_rowdims(), 
                              self.valuerange_coldims())

    def _create_instdict(self, instances, rowdims, coldims):
        for v in instances:
            rixes = tuple(self.dimindex_for_instance(dim, v) for dim in rowdims)
            cixes = tuple(self.dimindex_for_instance(dim, v) for dim in coldims)
            self.instdict[dimtable.CellIndex(tuple((rixes,cixes)))] = v

    def is_single_input(self):
        return len(self.inputdim) == 1

    def valuerange_cellindex(self, cix):
        if self.is_single_input(): 
            return dimtable.CellIndex(tuple((cix.row_indexes(), 
                                             cix.col_indexes())))
        else:
            return dimtable.CellIndex(tuple((cix.row_indexes()[:-1], 
                                             cix.col_indexes())))

    def input_index(self, cix):
        if self.is_single_input(): return 0
        else:                      return cix.row_indexes()[-1]
            

    def valuerange_rowdims(self): 
        if self.is_single_input(): return self.rowdims
        else:                      return self.rowdims[:-1]

    def valuerange_coldims(self): 
        return self.coldims

    def dimindex_for_instance(self, dim, inst):
        return (i for i,item in enumerate(dim.items) if item.matches_instance(inst)).next()

    def items_for_cellix(self, cellix):
        return (
            [self.rowdims[dix].items[rix] for dix, rix in enumerate(cellix[0])]
            +
            [self.coldims[dix].items[cix] for dix, cix in enumerate(cellix[1])]
            )

    def get(self, cellindex):
        cix = self.valuerange_cellindex(cellindex)
        return self.instdict.get(cix, None)

    def save(self, cellix, instance_id, value):
        if instance_id > 0:
            if value is None:
                # get all the other values and check if they are null
                self.delete(cellix, instance_id)
            else:
                self.update(cellix, instance_id, value)
        else: 
            if value is not None:
                self.create(cellix, value)

    def save_many(self, instance_id, valuedict):
        if instance_id > 0:
            if ((len(valuedict) == len(self.inputdim))
                and 
                all(v[0] is None for v in valuedict.values())):
                self.delete(valuedict.keys()[0], instance_id)
            else:
                self.update_from_many(instance_id, valuedict)
        else:
            if not all(v[0] is None for v in valuedict.values()):
                self.create_from_many(valuedict)

    def create(self, cellix, value):
        logger.debug("Creating instance %s" % (str(cellix)))
        instance = self.model()

        fix = self.input_index(cellix)
        setattr(instance, self.inputdim[fix], value)

        for rix, rdim in zip(cellix[0], self.valuerange_rowdims()):
            field     = rdim.fieldname
            field_val = rdim[rix]
            setattr(instance, field, field_val)

        for cix, cdim in zip(cellix[1], self.valuerange_coldims()):
            field     = cdim.fieldname
            field_val = cdim[cix]
            setattr(instance, field, field_val)

        for field, value in self.fixed_fields:
            setattr(instance, field, value)

        instance.save()

        self.instdict[cellix] = instance # update internal data structure

    def create_from_many(self, valuedict):
        logger.debug("Creating instance")
        instance = self.model()

        for cellix, value_and_default in valuedict.iteritems():
            value = value_and_default[0]
            default = value_and_default[1]

            fix = self.input_index(cellix)
            if value is None:
                if default is not django.db.models.fields.NOT_PROVIDED:
                    setattr(instance, self.inputdim[fix], default)
                else:
                    raise exceptions.ValidationError("Empty input and default value isn't provided")
            else:
                setattr(instance, self.inputdim[fix], value)


        thoseitems = [item for item in self.items_for_cellix(cellix)
                      if isinstance(item, ValueItem)]
        for item in thoseitems:
            
            field     = item.fieldname
            field_val = item.value()
            setattr(instance, field, field_val)

        # for rix, rdim in zip(cellix[0], self.valuerange_rowdims()):
        #     field     = rdim.fieldname
        #     field_val = rdim[rix]
        #     setattr(instance, field, field_val)

        # for cix, cdim in zip(cellix[1], self.valuerange_coldims()):
        #     field     = cdim.fieldname
        #     field_val = cdim[cix]
        #     setattr(instance, field, field_val)

        for field, value in self.fixed_fields:
            setattr(instance, field, value)

        instance.save()

        self.instdict[cellix] = instance # update internal data structure


    def delete(self, cellix, instance_id):
        logger.debug("Deleting instance %d %s" % (instance_id, 
                                                  str(cellix)))
        instance = self.model.objects.get(pk = instance_id)
        instance.delete()

        cix = self.valuerange_cellindex(cellix)
        self.instdict.pop(cix) # update internal data structure


    def update(self, cellix, instance_id, value):
        logger.debug("Updating instance %d %s" % (instance_id,
                                                  str(cellix)))
        instance = self.model.objects.get(pk = instance_id)

        fix = self.input_index(cellix)
        setattr(instance, self.inputdim[fix], value)
        instance.save()

        cix = self.valuerange_cellindex(cellix)
        self.instdict[cix] = instance # update internal data structure

    def update_from_many(self, instance_id, valuedict):
        logger.debug("Updating instance %d" % (instance_id))

        instance = self.model.objects.get(pk = instance_id)

        for cellix, value_and_default in valuedict.iteritems():
            value = value_and_default[0]
            default = value_and_default[1]

            fix = self.input_index(cellix)
            if value is None:
                if default is not django.db.models.fields.NOT_PROVIDED:
                    setattr(instance, self.inputdim[fix], default)
                else:
                    raise exceptions.ValidationError("Empty input and default value isn't provided")
            else:
                setattr(instance, self.inputdim[fix], value)

        instance.save()

        cix = self.valuerange_cellindex(cellix)
        self.instdict[cix] = instance # update internal data structure


class Presenter(object):
    def __init__(self, data, prefix):
        self.data = data
        #assert all(isinstance(item, InputItem) for item in self.data.inputdim.items)
        self.cell_fields  = [get_model_field(item.model, item.fieldname)
                             for item in self.data.inputdim.items 
                             if isinstance(item, InputItem)]
        self.cell_errors  = {} # indexed by cellindex
        self.other_errors = []

        #self._renderers = {}
        self._formfields = {}
        self.indexer = dimtable.Indexer(data.coldims, data.rowdims)
        self.prefix = prefix

    def formfield(self, fieldname):
        field = self._formfields.get(fieldname, None)
        if field is None:
            field  = self.get_field(fieldname).formfield()
            self._formfields[fieldname] = field
        return field

    # def renderer(self, fieldname):
    #     try:
    #         return self._renderers[fieldname]
    #     except KeyError:
    #         field = self.formfield(fieldname)
    #         if isinstance(field, django.forms.fields.IntegerField):
    #             renderer = IntegerCellRenderer(field)
    #         else:
    #             renderer = TextCellRenderer(field)
    #         self._renderers[fieldname] = renderer
    #         return renderer

    def get_field(self, fieldname):
        return self.data.model._meta.get_field_by_name(fieldname)[0]

    def is_related_field(self, fieldname):
        return isinstance(self.get_field(fieldname),
                          django.db.models.fields.related.RelatedField)

    def is_foreignkey(self, fieldname):
        return isinstance(self.get_field(fieldname),
                          django.db.models.fields.related.ForeignKey)

    def is_decimal_field(self, fieldname):
        return isinstance(self.get_field(fieldname),
                          django.db.models.fields.DecimalField)

    def instance_and_value_string(self, cellindex):
        # dict.get is used here instead of [] and try/except, as data is likely
        # to be sparse. It's about 30% faster in my tests with sparse data,
        # but with non-sparse data [] and try/except is faster
        # 
        # Savings are around 100ms for huge tables (50k cells)

        inst = self.data.get(cellindex)

        fix = self.data.input_index(cellindex)
        item = self.data.inputdim.items[fix]

        return inst, item.render_instance(inst, cellindex)


    # TODO(teemu): refactor
    def field_hidden_representation(self, field_name, value):
        field = self.get_field(field_name)
        if isinstance(field,
                      django.db.models.fields.related.ForeignKey):
            return unicode(value.id)
        elif isinstance(field,
                        django.db.models.fields.DateField):
            return value.strftime('%Y%m%d') 
        else:
            return unicode(value)

    def dim_hidden_representations(self, dim):
        # field = self.get_field(dim.field_name)
        # if isinstance(field,
        #               django.db.models.fields.related.ForeignKey):
        #     values = [str(v.id) for v in dim.values()]
        # elif isinstance(field,
        #                 django.db.models.fields.DateField):
        #     values = [d.strftime('%Y%m%d') for d in dim.values()]
        # else:
        #     values = [str(v) for v in dim.values()]
        return write_list([item.hidden_serialize() for item in dim.items 
                           if isinstance(item, ValueItem)])


    def render_fixed_data(self, prefix):
        output = []
        fixed = [(fieldname, value) for fieldname, value in self.data.fixed_fields]
        for fieldname, value in fixed:
            name     = u"_".join([prefix, 'fixed', fieldname])
            valuestr = self.field_hidden_representation(fieldname, value)
            output.append(html.hidden_input(name=name, value=valuestr))
        return u'\n'.join(output)

    def hidden_data_dimvalues(self, prefix):
        output = ["<!-- BEGIN hidden_data_dimvalues -->"]
        def dimension_values(dims, tag):
            for i, dim in enumerate(dims):
                if not isinstance(dim, InputDim):
                    name  = u"_".join([prefix, tag, 'values', str(i)])
                    value = self.dim_hidden_representations(dim)
                    output.append(html.hidden_input(name=name, value=value))

        dimension_values(self.data.rowdims, 'rdim')
        dimension_values(self.data.coldims, 'cdim')

        output.append("<!-- END hidden_data_dimvalues -->")
        return u'\n'.join(output)


    def cell_instance_ids(self):
        ids = []
        indexer = dimtable.Indexer(self.data.coldims, self.data.rowdims)
        for cellix, inst in self.data.instdict.iteritems():
            for ix, f in enumerate(self.data.inputdim):
                cix = dimtable.make_cellindex(cellix.row_indexes() + (ix,),
                                              cellix.col_indexes())
                cellint = indexer.cellindex_to_int(cix)
                ids.append((cellint, inst.id))
        return ids

    def hidden_data_instanceids(self, prefix):
        ids = json.dumps(self.cell_instance_ids())
        name  = u"_".join([prefix, "instanceids"])

        output = []
        output.append(html.hidden_input(name=name, value=ids))
        return u'\n'.join(output)

    def render_errors(self):
        output = []
        if self.cell_errors or self.other_errors:
            output.append('<ul class="dimtable errorlist">')
            for err in self.other_errors:
                if type(err.messages) == list:
                    for msg in err.messages:
                        output.append('<li>' + msg + '</li>')
                else:
                        output.append('<li>' + str(err.messages) + '</li>')

            for cellix, err in self.cell_errors.iteritems():
                for msg in err.messages():
                    output.append('<li>' + msg + '</li>')

            output.append('</ul>')
        return u"\n".join(output)

    def parse_cell_details(self, data, inst_id_str):
        try:
            cellix = int(data)
        except SyntaxError, err:
            logger.error("badly formatted cell index:" + data)
            raise err

        try:
            instance_id = int(inst_id_str)
        except ValueError, err:
            logger.error("badly formatted instance id:" + data)
            raise err
        return cellix, instance_id

    def validate_cell(self, cellix, valuestr):
        fix = self.data.input_index(cellix)
        value = None
        try:
            if valuestr or self.cell_fields[fix].empty_strings_allowed:
                value = self.cell_fields[fix].to_python(valuestr)            
        except exceptions.ValidationError, err:
            raise err
        return value

    def default_for_cell(self, cellix):
        fix = self.data.input_index(cellix)
        return self.cell_fields[fix].default

    def save_cell(self, cellix, instance_id, valuestr):
        try:
            value = self.validate_cell(cellix, valuestr)
            self.data.save(cellix, instance_id, value)
        except exceptions.ValidationError, err:
            self.cell_errors[cellix] = CellError(err, cellix, valuestr)
        except Exception, err:
            logger.error("Error: save_cell %s %s => %s " % (str(cellix),
                                                            valuestr,
                                                            unicode(err)))
            raise err

    def save_cells(self, cix, inputs):
        instance_id = inputs.values()[0][0]
        assert all([v[0] == instance_id for v in inputs.values()])
        
        # Validate all first
        valuedict = {}
        had_errors = False
        for cellix, inputdata in inputs.iteritems():
            instance_id, valuestr = inputdata
            try:
                value = self.validate_cell(cellix, valuestr)
                default = self.default_for_cell(cellix)
                valuedict[cellix] = (value, default)
            except exceptions.ValidationError, err:                
                self.cell_errors[cellix] = CellError(err, cellix, valuestr)
                had_errors = True
            except Exception, err:
                logger.error("Error: save_cells: validate_cell %s %s => %s " % 
                             (str(cellix),
                              valuestr,
                              unicode(err)))
                raise err
            
        if had_errors: return 

        self.data.save_many(instance_id, valuedict)
        #try:
        #    self.data.save_many(instance_id, values)
        # except Exception, err:
        #     logger.error("Error: save_cells failed %s => %s" % (str(instance_id), unicode(err)))
        #     # should add and show a table-wide error, but easier to debug db mismatches without.
        #     raise err



    def fast_td(self, id, content, cssclass = None, title = None):
        # we could use more versatile html.td, but this is a way faster
        classattr = ('class="%s"' % (cssclass)) if cssclass else ''
        titleattr = (u'title="%s"' % (title))   if title else ''
        idattr    = 'id="%s"' % (id)
        return u'<td %s %s %s>%s</td>' % (idattr, classattr, titleattr, content)

    def render_cell(self, cellindex, prefix, editable=False):
        inst, valuestr = self.instance_and_value_string(cellindex)

        cellint = self.indexer.cellindex_to_int(cellindex)
        ixstr = "_".join([prefix, 'cell', str(cellint)])
        
        cssclasses = set()
        title = None

        items = self.data.items_for_cellix(cellindex)

        if editable and all(item.editable() for item in items):
            cssclasses.add('editable')
        for item in items:
            
            cssclasses.update(item.css_classes())


        error = self.cell_errors.get(cellindex, None)
        if error:
            cssclasses.add('error')
            title = '&#10;'.join(error.messages())
            value = error.inputted_value

        return self.fast_td(ixstr, 
                            valuestr,
                            cssclass=' '.join(cssclasses),
                            title=title)

    def read_instanceids(self, args):
        name = u"_".join([self.prefix, "instanceids"]) 

        for key, value in args:
            if key == name:
                data = value
                instanceids = json.loads(data)
                return dict([(p[0], p[1]) for p in instanceids])
        return dict()
            
    def save_data(self, args):
        inputs_by_cix = ddict.Ddict(default = dict)

        instanceids = self.read_instanceids(args)
        
        for key,val in args:
            valuestr = val

            # Key parts are separated by '_' and follow the following format
            # <table-prefix>_<arg-category>_<category-arg-1>_<category-arg-2> ...
            keyparts = key.split('_')
            arg_category = keyparts[1]

            if arg_category == 'cell':
                cellint_str = keyparts[2]
                
                cellint = int(cellint_str)
                instance_id = instanceids.get(cellint, 0)
                #cellix , instance_id = self.parse_cell_details(cellint_str)
                cellix = self.indexer.int_to_cellindex(cellint)
                cix = self.data.valuerange_cellindex(cellix)

                inputs_by_cix[cix][cellix] = (instance_id, valuestr)

        for cix, inputs in inputs_by_cix.iteritems():
            self.save_cells(cix, inputs)

        return not (self.cell_errors or self.other_errors)

# ----------------------------------------------------------------------
# Table
# ----------------------------------------------------------------------
class Table(dimtable.Table):
    """
    Represents database rows of a Django Model as 2-dimensional table.
    Columns and rows both represent a field, all the other fields are fixed
    """

    def __init__(self,
                 data,
                 **kwargs):
        dimtable.Table.__init__(self, data.coldims, data.rowdims, **kwargs)
        self.data       = data

        self.presenter = kwargs.get('presenter', None)
        if self.presenter is None:
            self.presenter = Presenter(data, self.prefix)

        self.editable  = kwargs.get('editable', False)

    # ----------------------------------------------------------------------
    # Access cells
    # ----------------------------------------------------------------------

    def cell(self, cellindex):
        return self.presenter.render_cell(cellindex, 
                                          prefix   = self.prefix,
                                          editable = self.editable)
    

    # ----------------------------------------------------------------------
    # Rendering
    # ----------------------------------------------------------------------

    def hidden_inputs(self):
        rs = []

        # fixed 
        fixed = [(field, value) for field, value in self.data.fixed_fields]
        for name, value in fixed:

            fieldval = unicode(value)
            if self.is_foreignkey(name):
                fieldval = unicode(value.id)

            rs.append('<input type="hidden" name="%s_fixed_%s" value="%s">' 
                      % (self.prefix, name, fieldval))

        return mark_safe(u"\n".join(rs))


    def render_hidden(self):
        output = []
        output.append(self.presenter.hidden_data_instanceids(self.prefix))
        output.append(self.presenter.hidden_data_dimvalues(self.prefix))
        output.append(self.presenter.render_fixed_data(self.prefix))
        return mark_safe(u"\n".join(output))

    def render_errors(self):
        return mark_safe(self.presenter.render_errors())

    # Renders everything but the form wrapper and submit button
    def as_form(self):
        output = []
        output.append(self.render_hidden())
        output.append(self.render_errors())
        output.append(self.render())
        return mark_safe(u"\n".join(output))

    # Renders everything but the form wrapper and submit button
    def as_table(self):
        return self.render()

    def save(self, args):
        prefix = self.prefix + '_'
        table_args = [(key,val) 
                      for key,val in args.iteritems() if key.startswith(prefix)]
        return self.presenter.save_data(table_args)
            
        

   
