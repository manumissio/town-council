from templates.legistar_cms import LegistarCms

class San_Leandro(LegistarCms):
    """
    Spider for San Leandro, CA using the Legistar CMS template.
    """
    name = 'san_leandro'

    def __init__(self, *args, **kwargs):
        super().__init__(
            legistar_url='https://sanleandro.legistar.com/Calendar.aspx',
            city='san leandro',
            state='ca',
            *args, **kwargs
        )