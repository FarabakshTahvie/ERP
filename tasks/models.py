import os
import uuid
from django.conf import settings
from django.db import models
from utils.models import TimeStampedModel


def task_attachment_path(instance, filename):
    return f"tasks/{instance.task_id}/{uuid.uuid4().hex[:16]}{os.path.splitext(filename)[1].lower()}"


class Task(TimeStampedModel):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="tasks_created")

    class Meta:
        verbose_name = "وظیفه"
        verbose_name_plural = "وظایف"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class TaskSubtask(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="subtasks")
    title = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "زیروظیفه"
        verbose_name_plural = "زیروظایف"
        ordering = ["order", "pk"]

    def __str__(self):
        return self.title


class TaskAssignment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="assignments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="task_assignments")
    main_checked = models.BooleanField(default=False)
    note = models.CharField(max_length=1000, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "مسئول وظیفه"
        verbose_name_plural = "مسئولان وظایف"
        constraints = [models.UniqueConstraint(fields=["task", "user"], name="uniq_task_user")]

    def __str__(self):
        return f"{self.task} -> {self.user}"

    @property
    def checked_subtask_ids(self):
        return set(self.checks.values_list("subtask_id", flat=True))


class TaskSubtaskCheck(models.Model):
    assignment = models.ForeignKey(TaskAssignment, on_delete=models.CASCADE, related_name="checks")
    subtask = models.ForeignKey(TaskSubtask, on_delete=models.CASCADE, related_name="checks")
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "تیک زیروظیفه"
        verbose_name_plural = "تیک‌های زیروظایف"
        constraints = [models.UniqueConstraint(fields=["assignment", "subtask"], name="uniq_check")]

    def __str__(self):
        return f"{self.assignment} : {self.subtask}"


class TaskAttachment(TimeStampedModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=task_attachment_path)
    original_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "پیوست وظیفه"
        verbose_name_plural = "پیوست‌های وظایف"
        ordering = ["-created_at"]

    @property
    def is_image(self):
        return self.file.name.lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "webp", "bmp")
