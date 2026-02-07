from templates.legistar_cms import LegistarCms

class San_Mateo(LegistarCms):
    """
    Spider for San Mateo, CA using the Legistar CMS template.
    """
    name = 'san_mateo'

    def __init__(self, *args, **kwargs):
        super().__init__(
            legistar_url='https://cosm.legistar.com/Calendar.aspx',
            city='san mateo',
            state='ca',
            *args, **kwargs
        )