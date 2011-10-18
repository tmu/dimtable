# New API style for Dimtables that connect to Django models
# 
# Implementation notes: This is just a wrapper to provide new style API.
# Actual implementation is using the old API and old implementation from modeltable, 
# which is to be replaced later.

import modeltable
from modeltable import Dim

class Model: 
    def __init__(self, queryset):
        self.queryset = queryset

    def valueitems(self, fieldname, values, **kwargs):
        return modeltable.valueitems(self.queryset.model, fieldname, 
                                     values, **kwargs)

    def cellitem(self, fieldname, **kwargs):
        return modeltable.InputItem(self.queryset.model, fieldname, **kwargs)

    def djangomodel(self):
        return self.queryset.model

class Table(modeltable.Table):
    def __init__(self, model, celldim, rowdims, coldims, **kwargs):
        data = modeltable.Data(model.djangomodel(), 
                               modeltable.InputDim(celldim.items),
                               model.queryset,
                               rowdims, coldims, **kwargs)
        modeltable.Table.__init__(self, data, **kwargs)

