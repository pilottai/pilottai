import React from 'react';
import './Footer.css';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faTwitter, faGithub, faDiscord } from '@fortawesome/free-brands-svg-icons';

const Footer = () => {
    return (
        <footer>
            <div className="footer-content">
                <div className="footer-section">
                    <h4>PilottAI</h4>
                    <p>Building the future of multi-agent systems</p>
                </div>
                <div className="footer-section">
                    <h4>Links</h4>
                    <a href="#features">Features</a>
                    <a href="#docs">Documentation</a>
                    <a href="#pricing">Pricing</a>
                </div>
                <div className="footer-section">
                    <h4>Connect</h4>
                    <div className="social-links">
                        <a href="#" className="social-icon">
                            <FontAwesomeIcon icon={faTwitter} />
                            <span>Twitter</span>
                        </a>
                        <a href="#" className="social-icon">
                            <FontAwesomeIcon icon={faGithub} />
                            <span>GitHub</span>
                        </a>
                        <a href="#" className="social-icon">
                            <FontAwesomeIcon icon={faDiscord} />
                            <span>Discord</span>
                        </a>
                    </div>
                </div>
            </div>
            <div className="footer-bottom">
                <p>&copy; 2025 PilottAI. All rights reserved.</p>
            </div>
        </footer>
    );
};

export default Footer;
