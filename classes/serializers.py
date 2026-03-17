# classes/serializers.py
from rest_framework import serializers
from .models import Classroom, Student, Assignment, Grade


class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    average = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ['id', 'first_name', 'last_name', 'full_name', 'average', 'created_at']

    def get_average(self, obj):
        return obj.average()


class GradeSerializer(serializers.ModelSerializer):
    student_id = serializers.IntegerField(source='student.id', read_only=True)
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    effective_score = serializers.ReadOnlyField()

    class Meta:
        model = Grade
        fields = ['id', 'student_id', 'student_name', 'score', 'effective_score', 'comment']


class AssignmentSerializer(serializers.ModelSerializer):
    class_average = serializers.ReadOnlyField()
    graded_count = serializers.ReadOnlyField()

    class Meta:
        model = Assignment
        fields = [
            'id', 'name', 'assignment_type', 'date',
            'coefficient', 'max_score', 'global_bonus',
            'class_average', 'graded_count', 'created_at'
        ]


class ClassroomListSerializer(serializers.ModelSerializer):
    student_count = serializers.ReadOnlyField()
    class_average = serializers.SerializerMethodField()
    assignment_count = serializers.SerializerMethodField()

    class Meta:
        model = Classroom
        fields = [
            'id', 'name', 'subject', 'school_name', 'school_year',
            'student_count', 'assignment_count', 'class_average', 'created_at'
        ]

    def get_class_average(self, obj):
        return obj.class_average()

    def get_assignment_count(self, obj):
        return obj.assignments.count()


class ClassroomDetailSerializer(serializers.ModelSerializer):
    students = StudentSerializer(many=True, read_only=True)
    assignments = AssignmentSerializer(many=True, read_only=True)
    student_count = serializers.ReadOnlyField()
    class_average = serializers.SerializerMethodField()

    class Meta:
        model = Classroom
        fields = [
            'id', 'name', 'subject', 'school_name', 'school_year',
            'student_count', 'class_average',
            'students', 'assignments', 'created_at'
        ]

    def get_class_average(self, obj):
        return obj.class_average()
