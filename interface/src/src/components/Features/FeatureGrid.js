import React, { useEffect } from 'react';
import '@lottiefiles/lottie-player';
import './FeatureGrid.css';

const FeatureGrid = () => {
    useEffect(() => {
        // Ensure Lottie player is defined
        if (!customElements.get('lottie-player')) {
            import('@lottiefiles/lottie-player');
        }
    }, []);

    const features = [
        {
            icon: '🚀',
            title: 'Advanced Agent Architecture',
            items: [
                'Hierarchical multi-agent system',
                'Built-in task orchestration',
                'Flexible communication patterns',
                'Memory management'
            ]
        },
        {
            icon: '⚡',
            title: 'Enterprise Performance',
            items: [
                'Asynchronous processing',
                'Dynamic scaling',
                'Intelligent load balancing',
                'Fault tolerance'
            ]
        },
        {
            icon: '🔌',
            title: 'Seamless Integration',
            items: [
                'LLM provider support',
                'Extensible tool system',
                'Document processing',
                'WebSocket support'
            ]
        },
        {
            icon: '🛡️',
            title: 'Production Reliability',
            items: [
                'Comprehensive monitoring',
                'Error handling',
                'Resource optimization',
                'Advanced configuration'
            ]
        }
    ];

    const keyFeatures = [
        {
            icon: '🤖',
            title: 'Hierarchical Agent System',
            items: [
                'Manager and worker agent hierarchies',
                'Intelligent task routing',
                'Context-aware processing'
            ],
            animation: 'https://assets2.lottiefiles.com/packages/lf20_xyadoh9h.json',
            className: 'hierarchical-agents'
        },
        {
            icon: '🚀',
            title: 'Production Ready',
            items: [
                'Asynchronous processing',
                'Dynamic scaling',
                'Load balancing',
                'Fault tolerance'
            ],
            animation: 'https://assets8.lottiefiles.com/packages/lf20_xvrofzfk.json',
            className: 'production-ready'
        },
        {
            icon: '🧠',
            title: 'Advanced Memory',
            items: [
                'Semantic storage',
                'Task history tracking',
                'Context preservation',
                'Knowledge retrieval'
            ],
            animation: 'https://assets9.lottiefiles.com/packages/lf20_w51pcehl.json',
            className: 'advanced-memory'
        },
        {
            icon: '🔌',
            title: 'Integrations',
            items: [
                'Multiple LLM providers',
                'Document processing',
                'WebSocket support',
                'Custom tool integration'
            ],
            animation: 'https://assets3.lottiefiles.com/packages/lf20_zdtukd5q.json',
            className: 'integrations'
        }
    ];

    return (
        <>
            <section id="features" className="features">
                <h2>Advanced Features</h2>
                <div className="feature-grid">
                    {features.map((feature, index) => (
                        <div key={index} className="feature-card">
                            <div className="feature-icon">{feature.icon}</div>
                            <h3>{feature.title}</h3>
                            <ul>
                                {feature.items.map((item, itemIndex) => (
                                    <li key={itemIndex}>{item}</li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </div>
            </section>

            <section id="key-features" className="key-features">
                <div className="key-features-content">
                    <h2>Key Capabilities</h2>
                    <div className="features-container">
                        {keyFeatures.map((feature, index) => (
                            <div key={index} className={`feature-block ${feature.className}`}>
                                <div className="feature-icon">{feature.icon}</div>
                                <h3>{feature.title}</h3>
                                <ul>
                                    {feature.items.map((item, itemIndex) => (
                                        <li key={itemIndex}>{item}</li>
                                    ))}
                                </ul>
                                <div className="feature-animation">
                                    <lottie-player
                                        src={feature.animation}
                                        background="transparent"
                                        speed="1"
                                        loop
                                        autoplay
                                    ></lottie-player>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>
        </>
    );
};

export default FeatureGrid;