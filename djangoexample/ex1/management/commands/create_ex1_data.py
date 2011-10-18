import random
from django.core.management.base import BaseCommand, CommandError
from ex1.models import *

class Command(BaseCommand):
    args = ''
    help = 'Create a few employees and products' 
    def handle(self, *args, **options):
        firsts = [u"Juhani", u'Ville', u'Andy', u'Tommi', u'Teemu']
        lasts  = [u'Virtanen', u'Johnson', u'Tikkanen']
        
        for i in xrange(10):
            e = Employee.objects.create(first_name = random.choice(firsts),
                                        last_name  = random.choice(lasts))
            e.save()
            
        for p in ['iPhone 4S', 'Nokia N9', 'Galaxy S']:
            p = Product.objects.create(name = p)
            p.save()
        

 
