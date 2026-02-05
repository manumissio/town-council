from templates.legistar_cms import LegistarCms

class Berkeley(LegistarCms):
    """
    Web scraper for the Berkeley, CA City Council.
    
    This spider inherits from 'LegistarCms' because Berkeley uses the Legistar platform
    to host its meeting agendas and minutes. This template handles all the common
    logic for finding meetings, parsing dates, and extracting PDF links.
    """
    name = 'berkeley'

    def __init__(self, *args, **kwargs):
        # Initialize the spider with Berkeley's specific details.
        super(Berkeley, self).__init__(*args, city='berkeley', state='ca', **kwargs)
        
        # The URL where Berkeley publishes its meeting calendar.
        self.urls = ['https://berkeley.legistar.com/Calendar.aspx']
