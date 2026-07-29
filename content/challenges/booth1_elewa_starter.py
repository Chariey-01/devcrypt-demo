def validate_workflow(tasks):
    if tasks is None:
        return True

    expected = 1


    return expected == len(tasks)
