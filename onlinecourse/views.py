
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
import logging

from .models import Course, Enrollment, Question, Choice, Submission

logger = logging.getLogger(__name__)


# User registration
def registration_request(request):
    context = {}

    if request.method == 'GET':
        return render(
            request,
            'onlinecourse/user_registration_bootstrap.html',
            context
        )

    elif request.method == 'POST':
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']

        user_exist = User.objects.filter(username=username).exists()

        if not user_exist:
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                password=password
            )
            login(request, user)
            return redirect('onlinecourse:index')

        context['message'] = "User already exists."
        return render(
            request,
            'onlinecourse/user_registration_bootstrap.html',
            context
        )


# User login
def login_request(request):
    context = {}

    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']
        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')

        context['message'] = "Invalid username or password."
        return render(
            request,
            'onlinecourse/user_login_bootstrap.html',
            context
        )

    return render(
        request,
        'onlinecourse/user_login_bootstrap.html',
        context
    )


# User logout
def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


# Check whether a user is enrolled in a course
def check_if_enrolled(user, course):
    if user.is_authenticated:
        return Enrollment.objects.filter(
            user=user,
            course=course
        ).exists()

    return False


# Course listing
class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]

        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)

        return courses


# Course details
class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_detail_bootstrap.html'


# Enroll in a course
def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    is_enrolled = check_if_enrolled(user, course)

    if not is_enrolled and user.is_authenticated:
        Enrollment.objects.create(
            user=user,
            course=course,
            mode='honor'
        )
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(
        reverse(
            viewname='onlinecourse:course_details',
            args=(course.id,)
        )
    )


# Extract selected choice IDs from the submitted exam form
def extract_answers(request):
    submitted_answers = []

    for key in request.POST:
        if key.startswith('choice_'):
            value = request.POST[key]

            try:
                choice_id = int(value)
                submitted_answers.append(choice_id)
            except (ValueError, TypeError):
                continue

    return submitted_answers


# Submit an exam
@login_required
def submit(request, course_id):
    if request.method != 'POST':
        return redirect(
            'onlinecourse:course_details',
            pk=course_id
        )

    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    enrollment = get_object_or_404(
        Enrollment,
        user=user,
        course=course
    )

    submission = Submission.objects.create(
        enrollment=enrollment
    )

    selected_choice_ids = extract_answers(request)

    # Only save choices belonging to questions in this course.
    valid_choices = Choice.objects.filter(
        question__course=course,
        id__in=selected_choice_ids
    )

    submission.choices.set(valid_choices)

    return HttpResponseRedirect(
        reverse(
            viewname='onlinecourse:exam_result',
            args=(course_id, submission.id)
        )
    )


# Display the exam result
@login_required
def show_exam_result(request, course_id, submission_id):
    course = get_object_or_404(Course, pk=course_id)

    submission = get_object_or_404(
        Submission,
        id=submission_id,
        enrollment__course=course,
        enrollment__user=request.user
    )

    choices = submission.choices.all()

    total_score = 0
    questions = course.question_set.all()

    for question in questions:
        correct_choices = question.choice_set.filter(
            is_correct=True
        )

        selected_choices = choices.filter(
            question=question
        )

        # A question earns its grade only if all correct answers,
        # and no incorrect answers, were selected.
        if set(correct_choices) == set(selected_choices):
            total_score += question.grade

    context = {
        'course': course,
        'grade': total_score,
        'choices': choices,
    }

    return render(
        request,
        'onlinecourse/exam_result_bootstrap.html',
        context
    )
