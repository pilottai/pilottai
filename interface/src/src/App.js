import React from 'react';
import './App.css';
import Navbar from './components/Navigation/Navbar';
import Hero from './components/Hero/Hero';
import Features from './components/Features/FeatureGrid';
import Agents from './components/Agents/Agents';
import Performance from './components/Performance/Performance';
import Footer from './components/Footer/Footer';
import GlobalStyles from './styles/GlobalStyles';

function App() {
  return (
    <>
      <GlobalStyles />
      <div className="App">
        <div className="background-animation"></div>
        <Navbar />
        <Hero />
        <Features />
        <Agents />
        <Performance />
        <Footer />
      </div>
    </>
  );
}

export default App;