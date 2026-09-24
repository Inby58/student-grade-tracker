/**
 * Theme Manager for Student Grade Tracker
 * Supports light/dark mode toggling, persistent storage in localStorage,
 * system preference detection, and dynamic event dispatching for charts.
 */
(function () {
    const STORAGE_KEY = 'theme_preference';

    function getPreferredTheme() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored === 'dark' || stored === 'light') {
                return stored;
            }
        } catch (e) {
            // localStorage might be unavailable or blocked
        }
        return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    function updateToggleButtons(theme) {
        const isDark = theme === 'dark';
        const buttons = document.querySelectorAll('.theme-toggle-btn');
        buttons.forEach((btn) => {
            btn.setAttribute('aria-pressed', isDark ? 'true' : 'false');
            btn.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
            btn.setAttribute('title', isDark ? 'Switch to light mode' : 'Switch to dark mode');

            const textSpan = btn.querySelector('.theme-toggle-text');
            if (textSpan) {
                textSpan.textContent = isDark ? 'Light Mode' : 'Dark Mode';
            }

            const sunIcon = btn.querySelector('.sun-icon');
            const moonIcon = btn.querySelector('.moon-icon');
            if (sunIcon && moonIcon) {
                if (isDark) {
                    sunIcon.style.display = 'inline-flex';
                    moonIcon.style.display = 'none';
                } else {
                    sunIcon.style.display = 'none';
                    moonIcon.style.display = 'inline-flex';
                }
            }
        });
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        updateToggleButtons(theme);
        window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: theme } }));
    }

    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme') || getPreferredTheme();
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        try {
            localStorage.setItem(STORAGE_KEY, newTheme);
        } catch (e) {}
        applyTheme(newTheme);
    }

    // Expose global methods
    window.toggleTheme = toggleTheme;
    window.getCurrentTheme = function () {
        return document.documentElement.getAttribute('data-theme') || getPreferredTheme();
    };

    function init() {
        const activeTheme = document.documentElement.getAttribute('data-theme') || getPreferredTheme();
        applyTheme(activeTheme);

        document.querySelectorAll('.theme-toggle-btn').forEach(function (btn) {
            btn.removeEventListener('click', toggleTheme);
            btn.addEventListener('click', toggleTheme);
        });

        // React to system preference changes if user has not set a preference
        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
                try {
                    if (!localStorage.getItem(STORAGE_KEY)) {
                        applyTheme(e.matches ? 'dark' : 'light');
                    }
                } catch (err) {}
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
