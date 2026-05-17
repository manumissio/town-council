from templates.legistar_api import LegistarApi


class Sunnyvale(LegistarApi):
    """
    Spider for Sunnyvale, CA using the Legistar Web API.
    """
    name = 'sunnyvale'

    def __init__(self, *args, **kwargs):
        super().__init__(
            client='sunnyvaleca',
            city='sunnyvale',
            state='ca',
            *args,
            **kwargs,
        )

    def create_event_item(self, meeting_date, meeting_name, source_url, documents, meeting_type=None):
        event = super().create_event_item(
            meeting_date=meeting_date,
            meeting_name=meeting_name,
            source_url=source_url,
            documents=documents,
            meeting_type=meeting_type,
        )
        body_name = (meeting_type or meeting_name).removesuffix(" Meeting").strip()
        event["name"] = f"Sunnyvale, CA {body_name}"
        return event
