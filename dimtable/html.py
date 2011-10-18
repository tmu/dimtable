def lonetag(tag, **kwargs):
    attrs = ['%s="%s"' % (key, value) for key,value in kwargs.iteritems()]
    return u'<%s>' % (u' '.join([tag] + attrs))

def tagify(tag, content, **kwargs): 
    attrs = ['%s="%s"' % (key, value) for key,value in kwargs.iteritems()]
    return u'<%s>%s</%s>' % (u" ".join([tag] + attrs), unicode(content), tag)

def th(content, **kwargs): return tagify('th', content, **kwargs)
def td(content, **kwargs): return tagify('td', content, **kwargs)

def tr(content, **kwargs):
    if type(content) == list:
        return tagify('tr', u"".join(content), **kwargs)
    else:
        return tagify('tr', content, **kwargs)

def input(**kwargs): 
    return lonetag('input', **kwargs)

def text_input(**kwargs): 
    kwargs['type'] = 'text'
    return input(**kwargs)


def hidden_input(name, value):
    return u'<input type="hidden" name="%s" value="%s" />' % (name, value)

