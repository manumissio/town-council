from templates.legistar_cms import LegistarCms

class Hayward(LegistarCms):
    """
    Spider for Hayward, CA using the Legistar CMS template.
    """
    name = 'hayward'

    def __init__(self, *args, **kwargs):
        super().__init__(
            'https://hayward.legistar.com/Calendar.aspx',
            'hayward',
            'ca',
            *args,
            **kwargs,
        )
