from django.db import models

# Simple Django models for the demo

class Employee(models.Model):
    last_name    = models.CharField(max_length=100)
    first_name   = models.CharField(max_length=100)
    
    def __unicode__(self):
        return u" ".join([self.first_name, self.last_name])

    class Meta:
        ordering = ('last_name','first_name')


class Product(models.Model):
    name = models.CharField(max_length=50)

    def __unicode__(self):
        return self.name


class DailySale(models.Model):
    date        = models.DateField()
    employee    = models.ForeignKey(Employee)
    product     = models.ForeignKey(Product)
    amount      = models.IntegerField()
