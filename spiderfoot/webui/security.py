import cherrypy
import secure

def setup_security_headers():
    csp = (
        secure.ContentSecurityPolicy()
            .default_src("'self'")
            .script_src("'self'", "'unsafe-inline'", "blob:")
            .style_src("'self'", "'unsafe-inline'")
            .base_uri("'self'")
            .connect_src("'self'", "data:")
            .frame_src("'self'", 'data:')
            .img_src("'self'", "data:")
    )
    secure_headers = secure.Secure(
        server=secure.Server().set("server"),
        cache=secure.CacheControl().must_revalidate(),
        csp=csp,
        referrer=secure.ReferrerPolicy().no_referrer(),
    )
    cherrypy.config.update({
        "tools.response_headers.on": True,
        "tools.response_headers.headers": secure_headers.framework.cherrypy()
    })
