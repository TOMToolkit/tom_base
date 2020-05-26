# Authentication Exceptions

The TOM Toolkit offers a few custom exceptions that are documented in the API documentation, but one in particular 
should be noted.

For any modules exposing external services, such as brokers, harvesters, or facilities, a failed authentication should 
raise an `ImproperCredentialsException`. Exceptions of this type are caught by the TOM Toolkit's built-in 
`ExternalServiceMiddleware`. This middleware will display an error at the top of the page and redirect the user to the 
home page.