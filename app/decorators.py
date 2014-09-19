from threading import Thread


def async(f):
    def wrapper(*args, **kwargs):
        thr = Thread(target=f, args=args, kwargs=kwargs)
        thr.start()
    return wrapper
