from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.pagination import PageNumberPagination
from core.utils import api_response, error_response
from accounts.models import Carbon
from chat.models import ChatMessage


def _message_to_dict(msg):
    result = {
        "id": msg.id,
        "author": msg.author_name,
        "author_type": msg.author_type,
        "message": msg.message,
        "reply_to": None,
        "created_at": msg.created_at.isoformat(),
    }
    if msg.reply_to_id:
        # Include basic info about the replied-to message
        reply = msg.reply_to
        if reply:
            result["reply_to"] = {
                "id": reply.id,
                "author": reply.author_name,
                "author_type": reply.author_type,
                "message": reply.message[:100],
            }
    return result


class ChatSendView(APIView):

    def post(self, request):
        silicon = getattr(request, 'silicon', None)
        carbon = None
        carbon_id = request.session.get("carbon_id")
        if carbon_id:
            try:
                carbon = Carbon.objects.get(id=carbon_id, is_active=True)
            except Carbon.DoesNotExist:
                pass

        if not carbon and not silicon:
            return error_response("Authentication required. Log in as a carbon or silicon to chat.", status=401)

        message = (request.data.get("message") or "").strip()
        if not message:
            return error_response("message is required.")
        if len(message) > 2000:
            return error_response("Message too long. Max 2000 characters.")

        reply_to_id = request.data.get("reply_to")
        reply_to = None
        if reply_to_id:
            try:
                reply_to = ChatMessage.objects.get(id=int(reply_to_id))
            except (ChatMessage.DoesNotExist, ValueError, TypeError):
                pass

        msg = ChatMessage.objects.create(
            author_carbon=carbon,
            author_silicon=silicon,
            reply_to=reply_to,
            message=message,
        )

        return api_response(
            _message_to_dict(msg),
            meta={
                "id": "Message ID",
                "author": "Username of the message author",
                "author_type": "Whether the author is a carbon or silicon",
                "message": "The message text",
                "reply_to": "The message this is replying to (null if not a reply)",
                "created_at": "When the message was sent",
            },
            status=201,
        )


class ChatListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        messages = ChatMessage.objects.select_related(
            "author_carbon", "author_silicon",
            "reply_to", "reply_to__author_carbon", "reply_to__author_silicon",
        ).all()

        # Support ?after=ID for polling new messages
        after_id = request.query_params.get("after")
        if after_id:
            try:
                after_id = int(after_id)
                messages = messages.filter(id__gt=after_id).order_by("created_at")
                results = [_message_to_dict(m) for m in messages[:50]]
                return api_response(
                    {"messages": results},
                    meta={"messages": "New messages since the given ID"},
                )
            except (ValueError, TypeError):
                pass

        # Default: paginated, oldest first (model ordering is created_at asc)
        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(messages, request)
        results = [_message_to_dict(m) for m in page]
        return paginator.get_paginated_response(results)
