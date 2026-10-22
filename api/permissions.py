from rest_framework.permissions import BasePermission


class IsStaffOrSuperuser(BasePermission):
    """Same rule as manageXML.views.AdminStaffRequiredMixin."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and (user.is_staff or user.is_superuser)
        )
