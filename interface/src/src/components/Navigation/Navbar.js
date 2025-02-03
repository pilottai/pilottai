import React from 'react';
import styled from 'styled-components';

const NavContainer = styled.nav`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
`;

const Logo = styled.div`
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 1.5rem;
  font-weight: 700;

  img {
    height: 40px;
    width: auto;
    vertical-align: middle;
  }

  span {
    background: linear-gradient(90deg, #4776E6 0%, #8E54E9 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
  }
`;

const NavLinks = styled.div`
  display: flex;
  gap: 2rem;
  align-items: center;

  a {
    color: #4A5568;
    text-decoration: none;
    font-weight: 500;
    transition: color 0.3s ease;

    &:hover {
      color: #4776E6;
    }
  }
`;

const TryButton = styled.button`
  background: linear-gradient(90deg, #4776E6 0%, #8E54E9 100%);
  border: none;
  padding: 0.8rem 1.5rem;
  border-radius: 50px;
  color: white;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.3s ease;

  &:hover {
    transform: translateY(-2px);
  }
`;

const Navbar = () => {
  return (
    <NavContainer>
      <Logo>
        <img src="/logo.png" alt="PilottAI Logo" />
        <span>PilottAI</span>
      </Logo>
      <NavLinks>
        <a href="#features">Features</a>
        <a href="#architecture">Architecture</a>
        <a href="#documentation">Documentation</a>
        <a href="#contact">Contact</a>
        <TryButton>Try PilottAI</TryButton>
      </NavLinks>
    </NavContainer>
  );
};

export default Navbar;