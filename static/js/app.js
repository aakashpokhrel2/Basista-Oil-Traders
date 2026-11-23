/**
 * Petrol Station Management System - Interactive JavaScript
 * Handles sidebar toggling, HTMX CSRF injection, and dropdown interactions.
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Mobile Sidebar Toggle
    const mobileMenuBtn = document.getElementById('mobile-menu-toggle');
    const sidebar = document.getElementById('main-sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    if (mobileMenuBtn && sidebar && overlay) {
        function toggleSidebar() {
            const isClosed = sidebar.classList.contains('-translate-x-full');
            if (isClosed) {
                sidebar.classList.remove('-translate-x-full');
                overlay.classList.remove('hidden');
            } else {
                sidebar.classList.add('-translate-x-full');
                overlay.classList.add('hidden');
            }
        }

        mobileMenuBtn.addEventListener('click', toggleSidebar);
        overlay.addEventListener('click', toggleSidebar);
    }

    // 2. User dropdown menu toggle
    const userMenuBtn = document.getElementById('user-menu-button');
    const userMenuDropdown = document.getElementById('user-menu-dropdown');

    if (userMenuBtn && userMenuDropdown) {
        userMenuBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            userMenuDropdown.classList.toggle('hidden');
        });

        document.addEventListener('click', function (e) {
            if (!userMenuDropdown.contains(e.target) && !userMenuBtn.contains(e.target)) {
                userMenuDropdown.classList.add('hidden');
            }
        });
    }

    // 3. Language dropdown menu toggle
    const langBtn = document.getElementById('language-dropdown-button');
    const langDropdown = document.getElementById('language-dropdown');

    if (langBtn && langDropdown) {
        langBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            langDropdown.classList.toggle('hidden');
        });

        document.addEventListener('click', function (e) {
            if (!langDropdown.contains(e.target) && !langBtn.contains(e.target)) {
                langDropdown.classList.add('hidden');
            }
        });
    }

    // 4. Alert / Message dismiss button
    document.querySelectorAll('[data-dismiss="alert"]').forEach(button => {
        button.addEventListener('click', function () {
            const alert = this.closest('.alert-box');
            if (alert) {
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 200);
            }
        });
    });

    // 5. Setup HTMX CSRF token header
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    if (window.htmx) {
        document.body.addEventListener('htmx:configRequest', function (event) {
            const csrfToken = getCookie('csrftoken');
            if (csrfToken) {
                event.detail.headers['X-CSRFToken'] = csrfToken;
            }
        });
    }
});
