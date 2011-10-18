import operator
from string import maketrans 
from django.utils.safestring import mark_safe

import html
from html import *

# ----------------------------------------------------------------------
# DimItem
# ----------------------------------------------------------------------

class DimItem:
    def value(self): return None
    def representation(self): return u'n/a'
    def editable(self): return False
    def css_classes(self): return []
    
class EmptyItem(DimItem):
    def representation(self): return u''

class LabelItem(DimItem):
    def __init__(self, value, renderer = unicode):
        self._value = value
        self.renderer = renderer

    def value(self): return self._value
    def representation(self): return self.renderer(self._value)

def label_items(xs): return [LabelItem(x) for x in xs]

# ----------------------------------------------------------------------
# Dim is a single dimension of a multidimensional table,
# describing values of the dimension
# ----------------------------------------------------------------------
class Dim:
    def __init__(self, items):
        self.items = items

    def values(self):
        return [item.value() for item in self.items]

    def representations(self):        
        return [item.representation() for item in self.items]

    def __len__(self):
        return len(self.items)

    def __getitem__(self, ix):
        return self.items[ix].value()
    
# CellIndex derives from tuple and we should override new to support
# both old constctor syntax CellIndex(tuple((1,2),(1,)))
# and a better syntax CellIndex((1,2), (1,))
# Meanwhile, use this factory method for the latter case
def make_cellindex(rixes, cixes):
    return CellIndex(tuple((rixes, cixes)))

class CellIndex(tuple):
    def row_indexes(self): return self[0]
    def col_indexes(self): return self[1]

# ----------------------------------------------------------------------
# DimIter is a dimension iterator, that traverses dimensions 
# in a "reverse breadth first way", i.e. values of innermost 
# dimension are traversed first, then it's parent dimension is incremented
# and innermost dimension is again traversed and continuing
# recursively until outermost dimension is also fully traversed.
#
# TODO(teemu): Change to use pythonic iterator API. 
# TODO(teemu): It might also make sense to introduce cell iterator
#              that traversed the whole table in a correct order.
# ----------------------------------------------------------------------
class DimIter:
    def __init__(self, dims):
        self.dims = dims
        self.ixes = [0] * len(dims)
        self.finished = False

        # Optimization, we don't want to do these in next()
        # as it's called many times

        self._index_order = tuple(reversed(range(0, len(self.ixes))))
        self._lens = [len(dim) for dim in dims]

     # iterator should be changed to implement more,next,get

    def get(self):
        return tuple(self.ixes) #DimIndex(self.ixes)

    def end(self):
        return self.finished
    
    def next(self):
        for i in self._index_order:
            v = self.ixes[i] + 1
            if v == self._lens[i]:
                self.ixes[i] = 0
            else:
                self.ixes[i] = v
                return i
        self.finished = True
        return -1

    def first_of_group(self):
        return all(ix == 0 for ix in self.ixes[1:])
    
    def last_of_group(self):
        return all(ix == (length-1) for ix,length in zip(self.ixes[1:],
                                                     self._lens[1:]))

    def __repr__(self):
        return "DimIter(%s, %s)" % (str(self.ixes), self.finished)


def product(xs):
    return reduce(operator.mul, xs, 1)


class Indexer:
    def __init__(self, coldims, rowdims):
        self.coldims = coldims
        self.rowdims = rowdims 

    def cellindex_to_int(self, cix):
        return (
            sum(r 
                 * product(len(rdim) for rdim in self.rowdims[i+1:])
                 * product(len(cdim) for cdim in self.coldims)
                 for i,r in enumerate(cix.row_indexes()))
            + 
            sum(c
                * product(len(cdim) for cdim in self.coldims[j+1:])
                for j,c in enumerate(cix.col_indexes())))

    def int_to_cellindex(self, integer):
        v = integer
        cixes = []
        for cdim in reversed(self.coldims):
            m = len(cdim)
            c = v % m
            v = v / m
            cixes.append(c)

        rixes = []
        for rdim in reversed(self.rowdims):
            k = len(rdim)
            r = v % k
            v = v / k
            rixes.append(r)

        return make_cellindex(tuple(reversed(rixes)), tuple(reversed(cixes)))


class Data:
    def get(self, cellindex):
        return ''

# ----------------------------------------------------------------------
# Table is used to render a multidimensional HTML table
# ----------------------------------------------------------------------
class Table:
    def __init__(self, 
                 coldims,
                 rowdims,                 
                 **kwargs):
        self.coldims   = coldims if hasattr(coldims, '__iter__') else [coldims]
        self.rowdims   = rowdims if hasattr(rowdims, '__iter__') else [rowdims]
        self._data     = kwargs.get('data', None)

        self.css_class    = kwargs.get('css_class', 'dimtable')
        self.corner_title = kwargs.get('corner_title', '')
        self.prefix       = kwargs.get('prefix', 'table')
        self.indexer = Indexer(self.coldims, self.rowdims)

    # cell-method should be implemented by subclasses
    def cell(self, cellix):
        cellid = "table_cell_" + str(self.indexer.cellindex_to_int(cellix))
        celldata = unicode(self._data.get(cellix)) if self._data else u'n/a'
        return u''.join(['<td id="', cellid, '">', celldata, '</td>'])

    def colspan(self, ix):
        assert ix < len(self.coldims)
        if ix + 1 > len(self.coldims) - 1:
            return 1
        else:
            return len(self.coldims[ix + 1].values()) * self.colspan(ix + 1)

    def rowspan(self, ix):
        assert ix < len(self.rowdims)
        if ix + 1 > len(self.rowdims) - 1:
            return 1
        else:
            return len(self.rowdims[ix + 1].values()) * self.rowspan(ix + 1)


    def render_corner(self):
        return u'<th rowspan="%d" colspan="%d">%s</th>' % (len(self.coldims),
                                                           len(self.rowdims),
                                                           self.corner_title)

    def render_coldim_header(self,ix):
        dim = self.coldims[ix]
        cspan = self.colspan(ix)
        ths = []
        for item in dim.items:
            cssclasses     = item.css_classes()
            representation = item.representation()
            current = th(representation, 
                         **{'rowspan': cspan,
                            'class':  u' '.join(cssclasses)})
            ths.append(current)
        sub = u''.join(ths)

        x = 1
        for i in range(ix): x *= len(self.coldims[i].values())
        return sub * x

    def row_headers(self,dix, rixes):
        if dix == len(self.rowdims):
            return []

        dim = self.rowdims[dix]
        vix = rixes[dix]

        item = dim.items[vix]
        cssclasses     = item.css_classes()
        representation = item.representation()
        current = th(representation, 
                     **{'rowspan': self.rowspan(dix),
                        'class':  u' '.join(cssclasses)})
        return [current] + self.row_headers(dix + 1, rixes)
        
    def row_cells(self, rixes):
        tds = []
        citer = DimIter(self.coldims)
        while not citer.end():
            tds.append(self.cell(CellIndex(tuple((rixes, citer.get())))))
            citer.next()
            
        return tds

    def rows(self):
        riter = DimIter(self.rowdims)
        ths = self.row_headers(0, riter.get()) 
        tds = self.row_cells(riter.get())

        rs = [tr(ths + tds)]


        use_groups = len(self.rowdims) > 1

        while True:
            dix = riter.next()
            if riter.end(): break

            ths = self.row_headers(dix, riter.get())
            tds = self.row_cells(riter.get())

            if (use_groups):
                if riter.first_of_group():
                    attrs = {'class':'first-of-group'}
                elif riter.last_of_group():
                    attrs = {'class': 'last-of-group'}
                else:
                    attrs = {}
                rs.append(tr(ths + tds, **attrs))
            else:
                rs.append(tr(ths + tds))
        return rs

    def thead(self): 
        output = []
        output.append(u'<thead>')
        output.append(tr(self.render_corner() + self.render_coldim_header(0)))
        for cix,dim in enumerate(self.coldims[1:]):
            output.append(tr(self.render_coldim_header(cix+1)))
        output.append(u'</thead>')
        return u"\n".join(output)

    def tbody(self):
        output = []
        output.append(u'<tbody>')
        output.append(u'\n'.join(self.rows()))
        output.append(u'</tbody>')
        return u"\n".join(output)

    def tfoot(self):
        output = []
        output.append(u'<tfoot>')
        output.append(u'</tfoot>')
        return u"\n".join(output)

    def hidden_data_dimensions(self, prefix):
        output = ["<!-- BEGIN hidden_data_dimensions -->"]
        def dimension_data(dims, tag):
            # dimension count
            name  = u"_".join([prefix, tag, 'dimN'])
            value = str(len(dims))
            output.append(html.hidden_input(name=name, value=value))
            
            # dimension lengths
            for i, dim in enumerate(dims):
                name  = u"_".join([prefix, tag, 'length', str(i)])
                value = str(len(dim.values()))
                output.append(html.hidden_input(name=name, value=value))

        dimension_data(self.rowdims, 'rdim')
        dimension_data(self.coldims, 'cdim')

        output.append("<!-- END hidden_data_dimensions -->")
        return u'\n'.join(output)


    def render(self):
        output = []
        output.append(self.hidden_data_dimensions(self.prefix))
        output.append(u'<table class="%s">' % (self.css_class))
        output.append(self.thead())
        output.append(self.tbody())
        output.append(self.tfoot())
        output.append(u'</table>')
        return mark_safe(u"\n".join(output))

    def render_js(self):
        # TODO(teemu): This uses a hardcoded input field spec, 
        #              bring back from the old table implementation
        #              the ability to render input fields by field type
        return mark_safe(u"""
$(document).ready(function() {
   var create_input = function(val, name) {
       return $('<input type="text"/>').val(val).attr({size: 5, maxlength: 6, name: name});
   };
   dimtable.EditableTable({"create_input": create_input}); 
});
""")
