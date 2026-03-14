from templates.legistar_api import LegistarApi

class San_Mateo(LegistarApi):
    """
    Spider for San Mateo, CA using the Legistar Web API.
    """
    name = 'san_mateo'

    def __init__(self, *args, **kwargs):
        super().__init__(
            client='cosm',
            city='san mateo',
            state='ca',
            *args, **kwargs
        )
