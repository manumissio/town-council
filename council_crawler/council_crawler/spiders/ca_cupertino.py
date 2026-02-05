from templates.legistar_api import LegistarApi

class Cupertino(LegistarApi):
    """
    Spider for Cupertino, CA.
    
    Why this is improved:
    Instead of 'scraping' the website HTML (which breaks easily), this spider 
    talks directly to the Legistar Web API. This provides structured JSON data 
    and is much more resistant to website layout changes.
    """
    name = 'cupertino'

    def __init__(self, *args, **kwargs):
        # We pass 'cupertino' as the client name for the Legistar API
        super().__init__(client='cupertino', city='cupertino', state='ca', *args, **kwargs)

