from templates.legistar_cms import LegistarCms

class Sunnyvale(LegistarCms):
    """
    Spider for Sunnyvale, CA using the Legistar CMS template.
    """
    name = 'sunnyvale'

    def __init__(self, *args, **kwargs):
        super().__init__(
            legistar_url='https://sunnyvaleca.legistar.com/Calendar.aspx',
            city='sunnyvale',
            state='ca',
            *args, **kwargs
        )