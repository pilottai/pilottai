import { createGlobalStyle } from 'styled-components';

const GlobalStyles = createGlobalStyle`
  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  body {
    font-family: 'Poppins', sans-serif;
    background: #1a1a1a;
    color: #fff;
    overflow-x: hidden;
  }

  .container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 2rem;
  }

  button {
    padding: 0.8rem 2rem;
    background: linear-gradient(45deg, #ff6b6b, #ff8e53);
    border: none;
    border-radius: 30px;
    color: white;
    font-weight: bold;
    cursor: pointer;
    transition: transform 0.3s ease;

    &:hover {
      transform: scale(1.05);
    }
  }

  section {
    padding: 5rem 0;
  }
`;

export default GlobalStyles;