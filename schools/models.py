from django.db import models


class School(models.Model):
    name = models.CharField("学校名", max_length=100, unique=True)

    class Meta:
        verbose_name = "学校"
        verbose_name_plural = "学校"

    def __str__(self):
        return self.name
