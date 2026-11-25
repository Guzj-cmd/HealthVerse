package com.example.healthverse.filter;

import javax.servlet.Filter;
import javax.servlet.FilterChain;
import javax.servlet.FilterConfig;
import javax.servlet.ServletException;
import javax.servlet.ServletRequest;
import javax.servlet.ServletResponse;
import javax.servlet.annotation.WebFilter;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;

@WebFilter(urlPatterns = "/api/*")
public class ApiSecurityFilter implements Filter {
    @Override
    public void init(FilterConfig filterConfig) {
        // No mutable filter configuration.
    }

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        if (response instanceof HttpServletResponse) {
            HttpServletResponse http = (HttpServletResponse) response;
            http.setHeader("X-Frame-Options", "DENY");
            http.setHeader("X-Content-Type-Options", "nosniff");
            http.setHeader("Referrer-Policy", "no-referrer");
            http.setHeader("Permissions-Policy", "camera=(self), microphone=()");
        }
        chain.doFilter(request, response);
    }

    @Override
    public void destroy() {
        // No resources to release.
    }
}
