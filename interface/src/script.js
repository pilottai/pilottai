// Smooth scrolling for navigation links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        document.querySelector(this.getAttribute('href')).scrollIntoView({
            behavior: 'smooth'
        });
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

// Animation for feature cards
const observerOptions = {
    threshold: 0.1
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

// Stats counter animation
const statsObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            animateStats();
        }
    });
}, observerOptions);

document.querySelectorAll('.stat-card').forEach(stat => {
    statsObserver.observe(stat);
});

function animateStats() {
    document.querySelectorAll('.stat-card h3').forEach(stat => {
        const target = parseInt(stat.innerText);
        let current = 0;
        const increment = target / 50;
        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                clearInterval(timer);
                current = target;
            }
            stat.innerText = Math.round(current) + (stat.innerText.includes('%') ? '%' : '');
        }, 20);
    });
}

// Wave animation
const SEPARATION = 100, AMOUNTX = 50, AMOUNTY = 50;
let container;
let camera, scene, renderer;
let particles, particle, count = 0;
let mouseX = 0, mouseY = 0;
let windowHalfX = window.innerWidth / 2;
let windowHalfY = window.innerHeight / 2;

function init() {
    container = document.getElementById('canvas-container');
    
    camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 1, 10000);
    camera.position.z = 1000;
    
    scene = new THREE.Scene();
    particles = new Array();
    
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

    document.addEventListener('mousemove', onDocumentMouseMove, false);
    document.addEventListener('touchstart', onDocumentTouchStart, false);
    document.addEventListener('touchmove', onDocumentTouchMove, false);
    window.addEventListener('resize', onWindowResize, false);
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

function onDocumentTouchStart(event) {
    if (event.touches.length === 1) {
        event.preventDefault();
        mouseX = event.touches[0].pageX - windowHalfX;
        mouseY = event.touches[0].pageY - windowHalfY;
    }
}

function onDocumentTouchMove(event) {
    if (event.touches.length === 1) {
        event.preventDefault();
        mouseX = event.touches[0].pageX - windowHalfX;
        mouseY = event.touches[0].pageY - windowHalfY;
    }
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
