from templates.legistar_cms import LegistarCms

class Hayward(LegistarCms):
    """
    Spider for Hayward, CA using the Legistar CMS template.
    """
    name = 'hayward'

    def __init__(self, *args, **kwargs):
        super().__init__(
            legistar_url='https://hayward.legistar.com/Calendar.aspx',
            city='hayward',
            state='ca',
            *args, **kwargs
        )