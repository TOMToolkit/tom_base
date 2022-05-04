class ImproperCredentialsException(Exception):
    """
    The ImproperCredentialsException should be used when authentication fails with an external service. This exception
    is specifically caught by a TOM Toolkit middleware in order to render an appropriate error message.
    """
    pass
