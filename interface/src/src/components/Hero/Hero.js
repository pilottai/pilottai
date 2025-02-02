import React from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faGithub } from '@fortawesome/free-brands-svg-icons';
import './Hero.css';

const Hero = () => {
    return (
        <header className="hero">
            <div className="hero-content">
                <h1>Building Complex<br/>Multi-Agent Systems</h1>
                <div className="hero-description">
                    <p>Whether you're developing autonomous AI applications, distributed task processors, or intelligent automation systems, PilottAI provides the building blocks you need.</p>
                </div>
                <div className="cta-buttons">
                    <button className="primary-button">Get Started</button>
                    <a href="https://github.com/anuj0456/pilottai" className="github-button" target="_blank" rel="noopener noreferrer">
                        <FontAwesomeIcon icon={faGithub} />
                    </a>
                </div>
            </div>
            <div className="hero-visual">
                <div className="orbital-animation">
                    <div className="center-ball">
                        <span>PilottAI</span>
                    </div>
                    <div className="orbit orbit-1">
                        <div className="feature-ball" data-feature="Hierarchical Agent System">
                            <span>Hierarchical<br/>Agent</span>
                        </div>
                        <div className="feature-ball" data-feature="Production Ready Solution">
                            <span>Production<br/>Ready</span>
                        </div>
                    </div>
                    <div className="orbit orbit-2">
                        <div className="feature-ball" data-feature="Advanced Memory Management">
                            <span>Advanced<br/>Memory</span>
                        </div>
                        <div className="feature-ball" data-feature="Automatic Scaling Capability">
                            <span>Auto<br/>Scaling</span>
                        </div>
                    </div>
                    <div className="orbit orbit-3">
                        <div className="feature-ball" data-feature="Fast Processing Engine">
                            <span>Fast<br/>Processing</span>
                        </div>
                        <div className="feature-ball" data-feature="Smart System Integration">
                            <span>Smart<br/>Integration</span>
                        </div>
                    </div>
                </div>
            </div>
        </header>
    );
};

export default Hero;