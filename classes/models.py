# classes/models.py
from django.db import models
from django.conf import settings


class Classroom(models.Model):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='classrooms'
    )
    name = models.CharField(max_length=100)          # ex: "3ème B"
    subject = models.CharField(max_length=100)       # ex: "Mathématiques"
    school_name = models.CharField(max_length=200, blank=True, default='')  # ex: "Lycée Moderne"
    school_year = models.CharField(max_length=20, default='2024-2025')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        school = f" · {self.school_name}" if self.school_name else ""
        return f"{self.name} – {self.subject} ({self.school_year}){school}"

    @property
    def student_count(self):
        return self.students.count()

    def class_average(self):
        """Moyenne générale de la classe (moyenne des moyennes élèves)."""
        avgs = [s.average() for s in self.students.all()]
        avgs = [a for a in avgs if a is not None]
        if not avgs:
            return None
        return round(sum(avgs) / len(avgs), 2)


class Student(models.Model):
    classroom = models.ForeignKey(
        Classroom, on_delete=models.CASCADE, related_name='students'
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['last_name', 'first_name']
        unique_together = ('classroom', 'first_name', 'last_name')

    def __str__(self):
        return f"{self.last_name} {self.first_name}"

    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name}"

    def average(self):
        """Moyenne pondérée de l'élève, normalisée sur /20.
        Chaque note est ramenée sur 20 avant pondération pour permettre
        de comparer des devoirs sur des barèmes différents (/10, /20, etc.).
        """
        qs = self.grades.filter(
            score__isnull=False,
            assignment__classroom=self.classroom
        ).select_related('assignment')

        total_weighted = 0.0
        total_coeff = 0.0
        for grade in qs:
            a = grade.assignment
            if a.max_score == 0:
                continue
            effective = min(grade.score + a.global_bonus, a.max_score)
            effective = max(effective, 0)
            normalized = (effective / a.max_score) * 20  # ramène sur /20
            total_weighted += normalized * a.coefficient
            total_coeff += a.coefficient

        if total_coeff == 0:
            return None
        return round(total_weighted / total_coeff, 2)


class Assignment(models.Model):
    TYPE_CHOICES = [
        ('devoir', 'Devoir'),
        ('interrogation', 'Interrogation'),
        ('examen', 'Examen'),
    ]

    classroom = models.ForeignKey(
        Classroom, on_delete=models.CASCADE, related_name='assignments'
    )
    name = models.CharField(max_length=200)
    assignment_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default='devoir'
    )
    date = models.DateField()
    coefficient = models.FloatField(default=1.0)
    max_score = models.FloatField(default=20.0)
    global_bonus = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.name} ({self.classroom.name})"

    @property
    def class_average(self):
        """Moyenne de la classe pour ce devoir (bonus inclus)."""
        grades = self.grades.filter(score__isnull=False)
        if not grades.exists():
            return None
        scores = [
            min(g.score + self.global_bonus, self.max_score)
            for g in grades
        ]
        return round(sum(scores) / len(scores), 2)

    @property
    def graded_count(self):
        return self.grades.filter(score__isnull=False).count()


class Grade(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='grades'
    )
    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name='grades'
    )
    score = models.FloatField(null=True, blank=True)  # None = absent
    comment = models.TextField(blank=True)

    class Meta:
        unique_together = ('student', 'assignment')

    def __str__(self):
        return f"{self.student} – {self.assignment.name}: {self.score}"

    @property
    def effective_score(self):
        if self.score is None:
            return None
        return round(
            min(max(self.score + self.assignment.global_bonus, 0), self.assignment.max_score),
            2
        )


# ─────────────────────────────────────────────
# PRÉSENCE
# ─────────────────────────────────────────────

class AttendanceSession(models.Model):
    """Une séance d'appel (date + heure + classe)."""
    classroom = models.ForeignKey(
        Classroom, on_delete=models.CASCADE, related_name='attendance_sessions'
    )
    date = models.DateField()
    time = models.TimeField()
    label = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-time']

    def __str__(self):
        return f"{self.classroom.name} – {self.date} {self.time}"

    @property
    def present_count(self):
        return self.records.filter(is_present=True).count()

    @property
    def absent_count(self):
        return self.records.filter(is_present=False).count()

    @property
    def total_count(self):
        return self.records.count()


class AttendanceRecord(models.Model):
    """Présence d'un élève à une séance."""
    session = models.ForeignKey(
        AttendanceSession, on_delete=models.CASCADE, related_name='records'
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='attendance_records'
    )
    is_present = models.BooleanField(default=True)

    class Meta:
        unique_together = ('session', 'student')

    def __str__(self):
        status = "présent" if self.is_present else "absent"
        return f"{self.student} – {self.session.date}: {status}"
