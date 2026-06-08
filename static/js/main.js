document.addEventListener('DOMContentLoaded', function() {
    const hubLinks = document.querySelectorAll('.hub-toggle');
    const container = document.getElementById('hub-content');

    function clearNotifBadge() {
        const badge = document.querySelector('[data-hub="notifications"] .badge');
        if (badge) badge.remove();
    }

    function loadHub(hubType) {
        if (hubType === 'notifications') clearNotifBadge();

        hubLinks.forEach(link => {
            if (link.getAttribute('data-hub') === hubType) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });

        container.innerHTML = `
            <div class="d-flex justify-content-center align-items-center" style="min-height: 250px;">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        `;

        fetch(`/get-hub/${hubType}`)
            .then(response => {
                if (!response.ok) throw new Error('Unauthorized or missing hub');
                return response.text();
            })
            .then(html => {
                container.innerHTML = html;
            })
            .catch(err => {
                container.innerHTML = `
                    <div class="alert alert-danger border-0 shadow-sm d-flex align-items-center">
                        <i class="bi bi-exclamation-triangle-fill me-2"></i>
                        <div><strong>Access Denied:</strong> ${err.message}</div>
                    </div>
                `;
            });
    }

    hubLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const hubType = this.getAttribute('data-hub');

            const url = new URL(window.location);
            url.searchParams.set('hub', hubType);
            window.history.pushState({}, '', url);

            loadHub(hubType);
        });
    });

    // Check for query parameter on page load
    const urlParams = new URLSearchParams(window.location.search);
    const initialHub = urlParams.get('hub');
    if (initialHub) {
        let found = false;
        hubLinks.forEach(link => {
            if (link.getAttribute('data-hub') === initialHub) {
                found = true;
            }
        });
        if (found) {
            loadHub(initialHub);
        } else {
            const studentLink = document.querySelector('[data-hub="student"]');
            if (studentLink) {
                loadHub('student');
            }
        }
    } else {
        if (hubLinks.length > 0) {
            const studentLink = document.querySelector('[data-hub="student"]');
            if (studentLink) {
                studentLink.click();
            } else if (hubLinks[0]) {
                hubLinks[0].click();
            }
        }
    }
});


