from django.contrib import admin
from models import *

class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name')
    search_fields = ('last_name', 'first_name')

admin.site.register(Product)
admin.site.register(Employee, EmployeeAdmin)
    
