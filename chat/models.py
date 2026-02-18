from django.db import models
from accounts.models import Carbon, Silicon


class ChatMessage(models.Model):
    # One of these will be set, the other null
    author_carbon = models.ForeignKey(Carbon, null=True, blank=True, on_delete=models.SET_NULL, related_name="chat_messages")
    author_silicon = models.ForeignKey(Silicon, null=True, blank=True, on_delete=models.SET_NULL, related_name="chat_messages")
    message = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_messages"
        ordering = ["-created_at"]

    @property
    def author_type(self):
        if self.author_carbon:
            return "carbon"
        if self.author_silicon:
            return "silicon"
        return "unknown"

    @property
    def author_name(self):
        if self.author_carbon:
            return self.author_carbon.username
        if self.author_silicon:
            return self.author_silicon.username
        return "[deleted]"

    def __str__(self):
        return f"{self.author_name}: {self.message[:50]}"
