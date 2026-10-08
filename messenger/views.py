from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from core.capabilities import can, cap_required

from . import media, services

User = get_user_model()


def _json(action):
    try:
        data = action()
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True, **(data or {})})


def _int(raw):
    raw = (raw or "").strip()
    return int(raw) if raw.isdigit() else None


@cap_required("messenger.use")
@never_cache
@require_GET
def api_inbox(request):
    return JsonResponse({"ok": True, **services.inbox(request.user)})


@cap_required("messenger.use")
@require_POST
def api_open(request, user_id):
    other = get_object_or_404(User, pk=user_id, is_active=True)
    return _json(lambda: {"conv_id": services.open_direct(request.user, other).pk})


@cap_required("messenger.use")
@never_cache
@require_GET
def api_messages(request, conv_id):
    conv = services.get_conversation(request.user, conv_id)
    data = services.fetch_messages(request.user, conv, after=_int(request.GET.get("after")),
                                   before=_int(request.GET.get("before")), since=request.GET.get("since"))
    return JsonResponse({"ok": True, **data})


@cap_required("messenger.use")
@require_POST
def api_send(request, conv_id):
    conv = services.get_conversation(request.user, conv_id)

    def run():
        msg, created = services.send_message(
            request.user, conv, text=request.POST.get("text"), reply_to_id=_int(request.POST.get("reply_to")),
            client_uid=request.POST.get("client_uid", ""), attachment_ids=request.POST.get("attachment_ids"))
        return {"message": services.serialize_message(msg, request.user), "created": created}
    return _json(run)


@cap_required("messenger.use")
@require_POST
def api_read(request, conv_id):
    conv = services.get_conversation(request.user, conv_id)
    services.mark_read(request.user, conv, _int(request.POST.get("up_to")))
    return JsonResponse({"ok": True})


@cap_required("messenger.use")
@require_POST
def api_mute(request, conv_id):
    conv = services.get_conversation(request.user, conv_id)
    services.set_muted(request.user, conv, request.POST.get("muted") == "1")
    return JsonResponse({"ok": True})


@cap_required("messenger.use")
@require_POST
def api_edit(request, message_id):
    def run():
        msg = services.edit_message(request.user, message_id, request.POST.get("text"))
        return {"message": services.serialize_message(msg, request.user)}
    return _json(run)


@cap_required("messenger.use")
@require_POST
def api_delete(request, message_id):
    def run():
        msg = services.delete_message(request.user, message_id)
        return {"message": services.serialize_message(msg, request.user)}
    return _json(run)


@cap_required("messenger.use")
@require_POST
def api_pin(request, message_id):
    def run():
        msg = services.set_pinned(request.user, message_id, request.POST.get("pinned") == "1")
        return {"pins": services.pins_of(msg.conversation)}
    return _json(run)


@cap_required("messenger.use")
@require_POST
def api_upload(request, conv_id):
    conv = services.get_conversation(request.user, conv_id)

    def run():
        services.check_can_post(request.user, conv)
        att = media.save_upload(request.user, conv, request.FILES.get("file"),
                                voice=request.POST.get("voice") == "1", duration=request.POST.get("duration"))
        return {"attachment": media.serialize_attachment(att)}
    return _json(run)


@cap_required("messenger.use")
@never_cache
def page_inbox(request):
    return render(request, "messenger/inbox.html", {"inbox": services.inbox(request.user)})


@cap_required("messenger.use")
@never_cache
def page_chat(request, conv_id):
    conv = services.get_conversation(request.user, conv_id)
    return render(request, "messenger/chat.html", {
        "conv": conv,
        "meta": services.chat_meta(request.user, conv),
        "initial": services.fetch_messages(request.user, conv),
        "inbox": services.inbox(request.user),
        "can_moderate": can(request.user, "dashboard.manager"),
    })


@cap_required("messenger.use")
@never_cache
def page_profile(request):
    action = request.POST.get("action", "info")
    info_form = action not in ("avatar", "avatar_remove")
    values = None
    if request.method == "POST":
        try:
            if action == "avatar":
                services.set_avatar(request.user, request.FILES.get("avatar"))
                ok = "عکس پروفایل ذخیره شد."
            elif action == "avatar_remove":
                services.remove_avatar(request.user)
                ok = "عکس پروفایل حذف شد."
            else:
                services.update_profile(request.user, display_name=request.POST.get("display_name"),
                                        handle=request.POST.get("handle"))
                ok = "اطلاعات ذخیره شد."
        except ValueError as e:
            messages.error(request, str(e))
            if info_form:
                values = {"display_name": request.POST.get("display_name", ""),
                          "handle": request.POST.get("handle", "")}
        else:
            messages.success(request, ok)
            return redirect("messenger:profile")
    profile = services.get_profile(request.user)
    real_name = request.user.get_full_name() or request.user.username
    return render(request, "messenger/profile.html", {
        "values": values or {"display_name": profile.display_name, "handle": profile.handle},
        "avatar": services.avatar_url(request.user), "real_name": real_name,
        "initial": (profile.display_name or real_name)[:1],
    })
