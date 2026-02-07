from templates.legistar_cms import LegistarCms

class Mtn_View(LegistarCms):
    """
    Spider for Mountain View, CA using the Legistar CMS template.
    """
    name = 'mtn_view'

    def __init__(self, *args, **kwargs):
        super().__init__(
            legistar_url='https://mountainview.legistar.com/Calendar.aspx',
            city='mountain view',
            state='ca',
            *args, **kwargs
        )