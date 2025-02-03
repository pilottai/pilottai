import React from 'react';
import './Performance.css';

const Performance = () => {
    return (
        <section id="performance" className="performance">
            <h2>Why Choose PilottAI?</h2>
            <div className="stats-container">
                <div className="stat-card">
                    <h3>10x</h3>
                    <p>Faster Development</p>
                </div>
                <div className="stat-card">
                    <h3>99.9%</h3>
                    <p>Uptime</p>
                </div>
                <div className="stat-card">
                    <h3>24/7</h3>
                    <p>Support</p>
                </div>
            </div>
        </section>
    );
};

export default Performance;
