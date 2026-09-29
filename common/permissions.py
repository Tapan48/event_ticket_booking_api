from operator import attrgetter

from rest_framework.permissions import SAFE_METHODS, BasePermission


def _is_authenticated(user):
    return bool(user and user.is_authenticated)


class IsOrganizerOrReadOnly(BasePermission):
    """Anyone may read; writes need an organizer or staff account."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return _is_authenticated(user) and (user.is_staff or user.is_organizer)


class IsStaffOrReadOnly(BasePermission):
    """Anyone may read; only staff may write."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return _is_authenticated(request.user) and request.user.is_staff


class CanCheckIn(BasePermission):
    """Staff or organizers; whether it's *their* event is checked per ticket."""

    def has_permission(self, request, view):
        user = request.user
        return _is_authenticated(user) and (user.is_staff or user.is_organizer)


class IsOwnerOrReadOnly(BasePermission):
    """
    Object writes are limited to staff and the object's owner.

    The view names the owner with `owner_field`, which may be a dotted path
    (e.g. "event.organizer" for ticket types). Only the FK id is read, so this
    doesn't trigger an extra query for the owner row.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if not _is_authenticated(user):
            return False
        if user.is_staff:
            return True
        return attrgetter(f"{view.owner_field}_id")(obj) == user.pk
