class VerddUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        user.is_admin_or_staff = lambda: (
            user.is_superuser or user.is_staff if user.is_authenticated else False
        )
        response = self.get_response(request)
        return response
