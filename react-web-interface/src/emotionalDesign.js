import React from 'react';

// Function to apply emotional design principles to a component
export const applyEmotionalDesign = (Component, options) => {
  return (props) => {
    const { style, className, ...rest } = props;

    // Apply emotional design styles
    const emotionalStyle = {
      ...style,
      backgroundColor: options.backgroundColor || '#f0f0f0',
      color: options.color || '#333',
      borderRadius: options.borderRadius || '8px',
      padding: options.padding || '10px',
      boxShadow: options.boxShadow || '0 4px 8px rgba(0, 0, 0, 0.1)',
      transition: options.transition || 'all 0.3s ease',
      fontSize: options.fontSize || '16px',
      fontWeight: options.fontWeight || 'normal',
      textAlign: options.textAlign || 'center',
    };

    // Apply emotional design class names
    const emotionalClassName = `${className || ''} ${options.className || ''}`;

    return <Component style={emotionalStyle} className={emotionalClassName} {...rest} />;
  };
};

// Example usage of applyEmotionalDesign
const Button = (props) => <button {...props}>{props.children}</button>;

export const EmotionalButton = applyEmotionalDesign(Button, {
  backgroundColor: '#007bff',
  color: '#fff',
  borderRadius: '4px',
  padding: '12px 20px',
  boxShadow: '0 2px 4px rgba(0, 0, 0, 0.2)',
  transition: 'background-color 0.3s ease',
  fontSize: '14px',
  fontWeight: 'bold',
  textAlign: 'center',
});
