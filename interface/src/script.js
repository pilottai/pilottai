// Smooth scrolling for navigation links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            e.preventDefault();
            target.scrollIntoElement({
                behavior: 'smooth'
            });
        }
    });
});

// Navbar scroll effect
window.addEventListener('scroll', function() {
    const nav = document.querySelector('nav');
    if (window.scrollY > 50) {
        nav.style.background = 'rgba(15, 15, 26, 0.95)';
    } else {
        nav.style.background = 'transparent';
    }
});

// Mobile menu toggle
const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
if (mobileMenuToggle) {
    mobileMenuToggle.addEventListener('click', function() {
        const navLinks = document.querySelector('.nav-links');
        navLinks.classList.toggle('active');

        const icon = this.querySelector('i');
        if (icon.classList.contains('fa-bars')) {
            icon.classList.remove('fa-bars');
            icon.classList.add('fa-times');
        } else {
            icon.classList.add('fa-bars');
            icon.classList.remove('fa-times');
        }
    });
}

// Animation for feature cards
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

document.querySelectorAll('.feature-card').forEach(card => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(20px)';
    card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    observer.observe(card);
});

// Agent cards animation
document.querySelectorAll('.agent-card').forEach(card => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(20px)';
    card.style.transition = 'opacity 0.5s ease, transform 0.5s ease 0.1s';
    observer.observe(card);
});

// Tab functionality for code demo
document.querySelectorAll('.tab-button').forEach(button => {
    button.addEventListener('click', () => {
        // Remove active class from all buttons and panels
        document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.code-panel').forEach(panel => panel.classList.remove('active'));

        // Add active class to clicked button
        button.classList.add('active');

        // Show corresponding panel
        const tabId = button.getAttribute('data-tab');
        const panel = document.getElementById(`${tabId}-panel`);
        if (panel) {
            panel.classList.add('active');
        }
    });
});

// Copy button functionality
document.querySelectorAll('.copy-button').forEach(button => {
    button.addEventListener('click', () => {
        const codeBlock = button.closest('.code-demo-container').querySelector('.code-panel.active code');
        if (codeBlock) {
            navigator.clipboard.writeText(codeBlock.textContent.trim())
                .then(() => {
                    // Show copied confirmation
                    button.innerHTML = '<i class="fas fa-check"></i> Copied!';
                    setTimeout(() => {
                        button.innerHTML = '<i class="fas fa-copy"></i> Copy';
                    }, 2000);
                })
                .catch(err => {
                    console.error('Failed to copy text: ', err);
                });
        }
    });
});

// Scroll to top button
const scrollBtn = document.querySelector('.scrolltop');
if (scrollBtn) {
    window.addEventListener('scroll', () => {
        if (window.scrollY > 300) {
            scrollBtn.classList.add('show');
        } else {
            scrollBtn.classList.remove('show');
        }
    });

    scrollBtn.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}

// Example command input switcher
const swapBtn = document.querySelector('.swap-btn');
if (swapBtn) {
    const commands = [
        "Analyze market trends and create a summary report",
        "Process quarterly financial documents and extract key metrics",
        "Handle customer support tickets and prioritize by urgency",
        "Draft marketing emails for our new product launch"
    ];
    let currentCommand = 0;

    swapBtn.addEventListener('click', () => {
        currentCommand = (currentCommand + 1) % commands.length;
        const commandInput = document.querySelector('.command-input input');
        if (commandInput) {
            commandInput.value = commands[currentCommand];

            // Add animation
            commandInput.style.opacity = 0;
            setTimeout(() => {
                commandInput.style.opacity = 1;
            }, 200);
        }
    });
}

// Interactive wave animation for background
const initWaveAnimation = () => {
    const container = document.getElementById('canvas-container');
    if (!container || !window.THREE) return;

    const SEPARATION = 100, AMOUNTX = 40, AMOUNTY = 40;
    let camera, scene, renderer;
    let particles, particle, count = 0;
    let mouseX = 0, mouseY = 0;
    let windowHalfX = window.innerWidth / 2;
    let windowHalfY = window.innerHeight / 2;

    function init() {
        camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 1, 10000);
        camera.position.z = 1000;

        scene = new THREE.Scene();

        particles = [];

        const PI2 = Math.PI * 2;
        const material = new THREE.SpriteMaterial({
            color: 0xffffff,
            program: function(context) {
            context.beginPath();
            context.arc(0, 0, 0.4, 0, PI2, true);
            context.fill();
        }
        });

        let i = 0;
        for (let ix = 0; ix < AMOUNTX; ix++) {
            for (let iy = 0; iy < AMOUNTY; iy++) {
                particle = particles[i++] = new THREE.Sprite(material);
                particle.position.x = ix * SEPARATION - ((AMOUNTX * SEPARATION) / 2);
                particle.position.z = iy * SEPARATION - ((AMOUNTY * SEPARATION) / 2);
                scene.add(particle);
            }
        }

        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.setSize(window.innerWidth, window.innerHeight);
        container.appendChild(renderer.domElement);

        document.addEventListener('mousemove', onDocumentMouseMove);
        window.addEventListener('resize', onWindowResize);
    }

    function onWindowResize() {
        windowHalfX = window.innerWidth / 2;
        windowHalfY = window.innerHeight / 2;

        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    }

    function onDocumentMouseMove(event) {
        mouseX = event.clientX - windowHalfX;
        mouseY = event.clientY - windowHalfY;
    }

    function animate() {
        requestAnimationFrame(animate);
        render();
    }

    function render() {
        camera.position.x += (mouseX - camera.position.x) * 0.05;
        camera.position.y += (-mouseY - camera.position.y) * 0.05;
        camera.lookAt(scene.position);

        let i = 0;
        for (let ix = 0; ix < AMOUNTX; ix++) {
            for (let iy = 0; iy < AMOUNTY; iy++) {
                particle = particles[i++];
                particle.position.y = (Math.sin((ix + count) * 0.3) * 50) + (Math.sin((iy + count) * 0.5) * 50);
                particle.scale.x = particle.scale.y = (Math.sin((ix + count) * 0.3) + 1) * 2 + (Math.sin((iy + count) * 0.5) + 1) * 2;
            }
        }

        renderer.render(scene, camera);
        count += 0.1;
    }

    init();
    animate();
};

// Stats counter animation
const animateNumbers = () => {
    const statsObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const statElements = entry.target.querySelectorAll('.count');
                statElements.forEach(stat => {
                    const targetValue = stat.getAttribute('data-target') || stat.textContent;
                    const duration = 2000; // ms
                    let startTimestamp = null;
                    const startValue = 0;

                    // Check if the target is a number or has special chars
                    const isNumeric = !isNaN(parseInt(targetValue));

                    if (isNumeric) {
                        const step = (timestamp) => {
                            if (!startTimestamp) startTimestamp = timestamp;
                            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
                            const value = Math.floor(progress * (parseInt(targetValue) - startValue) + startValue);
                            stat.textContent = value;

                            if (progress < 1) {
                                window.requestAnimationFrame(step);
                            } else {
                                stat.textContent = targetValue;
                            }
                        };

                        window.requestAnimationFrame(step);
                    }
                });
            }
        });
    }, { threshold: 0.5 });

    // Observe hero stats if they exist
    const heroStatsSection = document.querySelector('.hero-stats');
    if (heroStatsSection) {
        statsObserver.observe(heroStatsSection);
    }
};

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initWaveAnimation();
    animateNumbers();
});


// Add this to your script.js file

// Fetch GitHub stars count
async function fetchGitHubStars() {
    try {
        const response = await fetch('https://api.github.com/repos/anuj0456/pilottai');
        const data = await response.json();

        if (data.stargazers_count !== undefined) {
            // Find all elements with the github-stars class and update them
            const starsElements = document.querySelectorAll('.github-stars');
            starsElements.forEach(element => {
                element.textContent = data.stargazers_count.toLocaleString();
            });

            // Update any GitHub buttons to include the star count
            const githubButtons = document.querySelectorAll('.github-button');
            githubButtons.forEach(button => {
                if (!button.querySelector('.github-stars')) {
                    const buttonText = button.innerHTML;
                    if (buttonText.includes('Star on GitHub')) {
                        button.innerHTML = `<i class="fab fa-github"></i> Star on GitHub <span class="github-star-count">${data.stargazers_count.toLocaleString()}</span>`;
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error fetching GitHub stars:', error);
    }
}

// Call this function when the page loads
document.addEventListener('DOMContentLoaded', function() {
    fetchGitHubStars();
});


// Pricing tab functionality
document.querySelectorAll('.pricing-tab-btn').forEach(button => {
    button.addEventListener('click', () => {
        // Remove active class from all buttons and sections
        document.querySelectorAll('.pricing-tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.pricing-section').forEach(section => section.classList.remove('active'));

        // Add active class to clicked button
        button.classList.add('active');

        // Show corresponding section
        const tabId = button.getAttribute('data-tab');
        document.getElementById(`${tabId}-pricing`).classList.add('active');
    });
});

// Toggle between monthly and yearly billing
const toggleSwitch = document.querySelector('.toggle-switch');
const billingOptions = document.querySelectorAll('.billing-option');
const toggleSlider = document.querySelector('.toggle-slider');

toggleSwitch.addEventListener('click', () => {
    billingOptions.forEach(option => option.classList.toggle('active'));
    toggleSlider.classList.toggle('monthly');
    toggleSlider.classList.toggle('yearly');

    // Toggle price display
    if (toggleSlider.classList.contains('yearly')) {
        document.querySelectorAll('.monthly-price').forEach(el => el.style.display = 'none');
        document.querySelectorAll('.yearly-price').forEach(el => el.style.display = 'block');
    } else {
        document.querySelectorAll('.monthly-price').forEach(el => el.style.display = 'block');
        document.querySelectorAll('.yearly-price').forEach(el => el.style.display = 'none');
    }
});

// Mobile menu functionality
const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
if (mobileMenuToggle) {
    mobileMenuToggle.addEventListener('click', function() {
        const navLinks = document.querySelector('.nav-links');
        navLinks.classList.toggle('active');

        const icon = this.querySelector('i');
        if (icon.classList.contains('fa-bars')) {
            icon.classList.remove('fa-bars');
            icon.classList.add('fa-times');
        } else {
            icon.classList.add('fa-bars');
            icon.classList.remove('fa-times');
        }
    });
}

// Scroll to top functionality
const scrollBtn = document.querySelector('.scrolltop');
if (scrollBtn) {
    window.addEventListener('scroll', () => {
        if (window.scrollY > 300) {
            scrollBtn.classList.add('show');
        } else {
            scrollBtn.classList.remove('show');
        }
    });

    scrollBtn.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}

// Add responsive styles for mobile nav
if (!document.head.querySelector('style[data-responsive="true"]')) {
    const style = document.createElement('style');
    style.setAttribute('data-responsive', 'true');
    style.textContent = `
        @media (max-width: 768px) {
            .nav-links {
                display: none;
                position: absolute;
                top: 80px;
                left: 0;
                width: 100%;
                background: rgba(15, 15, 26, 0.95);
                flex-direction: column;
                padding: 20px;
                gap: 15px;
                backdrop-filter: blur(10px);
            }

            .nav-links.active {
                display: flex;
            }

            .mobile-menu-toggle {
                display: block !important;
            }
        }
    `;
    document.head.appendChild(style);
}

