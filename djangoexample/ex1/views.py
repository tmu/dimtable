import datetime

from django.shortcuts import render_to_response
from django.db.models import Q, Sum, Avg, Count
from django.template  import RequestContext
from django.http      import (HttpResponse, HttpResponseRedirect,
                              HttpResponseBadRequest, Http404)

from models import * 
from dimtable.django_dimtable import Model, Table, Dim


def edit_sales(request):
    title = "Edit sales" 

    employees = Employee.objects.all()
    products  = Product.objects.all()

    today = datetime.date.today()
    dates = [today + datetime.timedelta(x) for x in xrange(7)]

    sales = DailySale.objects.filter( Q(date__gte = dates[0]) & 
                                      Q(date__lte = dates[-1]))

    def show_date(d): return d.strftime("%a %d/%m")


    model = Model(sales)
    table = Table(model = model,
                  celldim = Dim([model.cellitem('amount')]),
                  rowdims = [Dim(model.valueitems('employee', employees)),
                             Dim(model.valueitems('product', products))],
                  coldims = [Dim(model.valueitems('date', dates, renderer=show_date))],
                  editable=True
                  )
    if request.method == 'POST':
        ok = table.save(request.POST)
        if ok: 
            return HttpResponseRedirect('')


    return render_to_response('edit_sales_view.html', locals(), 
                              context_instance=RequestContext(request))


