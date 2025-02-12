import React, { useState } from 'react';
import './Agents.css';

const Agents = () => {
    const [command, setCommand] = useState("Build the target application based on the input requirements document.");
    
    // Removed placeholder avatar data URL
    
    const agents = [
        {
            name: "Thomas",
            role: "AI Research Lead",
            avatar: "/a1.png",
            expertise: "Machine Learning, Neural Networks",
            experience: "8+ years in AI",
            focus: "Advanced AI Architectures",
            skills: "Python, TensorFlow, PyTorch"
        },
        {
            name: "Mike",
            role: "Team Leader",
            avatar: "/a1.png",
            expertise: "Team Management, Strategy",
            experience: "10+ years",
            focus: "Team Coordination",
            skills: "Leadership, Planning"
        },
        {
            name: "Alice",
            role: "Product Manager",
            avatar: "/a1.png",
            expertise: "Product Strategy",
            experience: "6+ years",
            focus: "User Experience",
            skills: "Agile, Roadmapping"
        },
        {
            name: "Bob",
            role: "Architect",
            avatar: "/a1.png",
            expertise: "System Architecture",
            experience: "8+ years",
            focus: "Scalable Systems",
            skills: "Java, Spring, AWS"
        },
        {
            name: "Eve",
            role: "Project Manager",
            avatar: "/a1.png",
            expertise: "Project Management",
            experience: "10+ years",
            focus: "Project Planning",
            skills: "Agile, Scrum, Jira"
        },
        {
            name: "Alex",
            role: "Engineer",
            avatar: "/a1.png",
            expertise: "Software Development",
            experience: "6+ years",
            focus: "Front-end Development",
            skills: "JavaScript, React, Angular"
        },
        {
            name: "Edward",
            role: "QA Engineer",
            avatar: "/a1.png",
            expertise: "Quality Assurance",
            experience: "8+ years",
            focus: "Test Automation",
            skills: "Selenium, Appium, JUnit"
        },
        {
            name: "David",
            role: "Data Analyst",
            avatar: "/a1.png",
            expertise: "Data Analysis",
            experience: "6+ years",
            focus: "Data Visualization",
            skills: "Excel, Tableau, Power BI"
        },
        {
            name: "Swen",
            role: "Issue Solver",
            avatar: "/a1.png",
            expertise: "Problem Solving",
            experience: "10+ years",
            focus: "Critical Thinking",
            skills: "Analytical Thinking, Creative Problem Solving"
        },
        {
            name: "Charlie",
            role: "DevOps Engineer",
            avatar: "/a1.png",
            expertise: "Infrastructure & Automation",
            experience: "7+ years",
            focus: "CI/CD & Cloud",
            skills: "Docker, Kubernetes, Jenkins"
        }
    ];

    const handleSwap = () => {
        const commands = [
            "Build the target application based on the input requirements document.",
            "Analyze and optimize the existing codebase for better performance.",
            "Design and implement a new feature based on user feedback.",
            "Debug and fix reported issues in the production environment."
        ];
        const currentIndex = commands.indexOf(command);
        const nextIndex = (currentIndex + 1) % commands.length;
        setCommand(commands[nextIndex]);
    };

    return (
        <section id="agents" className="agents-section">
            <h2>Meet Your AI Team</h2>
            <p className="section-subtitle">Your first Private software company team solving complex challenges</p>
            
            <div className="command-input">
                <span className="command-icon">⌘</span>
                <input type="text" value={command} readOnly />
                <button className="swap-btn" onClick={handleSwap}>Swap</button>
            </div>

            <div className="agents-grid">
                {agents.map((agent, index) => (
                    <div key={index} className="agent-card">
                        <div className="card-inner">
                            <div className="card-front">
                                <div className="agent-avatar">
                                    <img src={agent.avatar} alt={agent.name} />
                                </div>
                                <div className="agent-info">
                                    <h3>{agent.name}</h3>
                                    <span className="agent-role">{agent.role}</span>
                                </div>
                            </div>
                            <div className="card-back">
                                <h3>{agent.name}</h3>
                                <div className="agent-details">
                                    <p className="detail-item"><strong>Expertise:</strong> {agent.expertise}</p>
                                    <p className="detail-item"><strong>Experience:</strong> {agent.experience}</p>
                                    <p className="detail-item"><strong>Focus:</strong> {agent.focus}</p>
                                    <p className="detail-item"><strong>Skills:</strong> {agent.skills}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
};

export default Agents;
