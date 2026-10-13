class GermanByDefaultMiddleware:
    """Ignore the browser's language so the app starts in German for everyone.

    Django would otherwise follow Accept-Language, and a phone or PC set to
    English shows the whole app (and writes analyses and plans) in English.
    Choosing EN in the header still works: that sets the language cookie, which
    LocaleMiddleware reads before the header.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.META.pop("HTTP_ACCEPT_LANGUAGE", None)
        return self.get_response(request)
