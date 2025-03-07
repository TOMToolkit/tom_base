from django.shortcuts import render, redirect
from django_tasks import task, default_task_backend
import time

WORK_TIME = 3


@task
def calculate_meaning_of_life() -> int:
    time.sleep(WORK_TIME)  # Fake work
    return 42


def question_meaning_of_life(request):
    context = {'backend': default_task_backend, 'work_time': WORK_TIME}
    return render(request, 'tom_async_demo/question.html', context)


def start_meaning_of_life(request):
    result = calculate_meaning_of_life.enqueue()
    # This is kinda lame, need to support the case of immediate vs deferred results
    # because the database backend does not support immediate mode.
    if default_task_backend.supports_get_result:
        return redirect('async:answer', result_id=result.id)
    else:
        return render(request, 'tom_async_demo/partials/result_row.html', {'result': result})


def get_meaning_of_life(request, result_id):
    result = calculate_meaning_of_life.get_result(result_id)
    return render(request, 'tom_async_demo/partials/result_row.html', {'result': result})
