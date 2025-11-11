/**
 * API Documentation JavaScript Functions
 * Enhanced copy functionality with visual feedback and accordion system
 */

// Prevent accordion errors by checking if elements exist
document.addEventListener('DOMContentLoaded', function() {
    // Disable problematic accordion if no container exists
    const accordionContainer = document.querySelector('.accordion-container');
    if (!accordionContainer) {
        // Override accordion initialization to prevent errors
        if (window.Accordion) {
            console.log('Accordion container not found, skipping initialization');
        }
    }
});

// Global copy function with enhanced feedback
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showCopyNotification('Copié dans le presse-papiers !', 'success');
        
        // Visual feedback on button if available
        if (event && event.target) {
            const button = event.target.closest('.api-copy-btn');
            if (button) {
                button.classList.add('copied');
                const span = button.querySelector('span');
                const originalText = span ? span.textContent : '';
                if (span) span.textContent = 'Copié !';
                
                setTimeout(() => {
                    button.classList.remove('copied');
                    if (span) span.textContent = originalText || 'Copier';
                }, 2000);
            }
        }
        
        console.log('Successfully copied to clipboard:', text.substring(0, 100) + '...');
    }).catch(function(err) {
        console.error('Failed to copy using Clipboard API: ', err);
        
        // Fallback for older browsers
        try {
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            textArea.style.top = '-999999px';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            
            const successful = document.execCommand('copy');
            document.body.removeChild(textArea);
            
            if (successful) {
                showCopyNotification('Copié dans le presse-papiers !', 'success');
                console.log('Successfully copied using fallback method');
            } else {
                showCopyNotification('Erreur lors de la copie', 'error');
            }
        } catch (fallbackErr) {
            console.error('Fallback copy failed: ', fallbackErr);
            showCopyNotification('Copie non supportée par ce navigateur', 'error');
        }
    });
}

// Show copy notification
function showCopyNotification(message, type = 'success') {
    // Remove existing notification if any
    const existingNotification = document.getElementById('copyNotification');
    if (existingNotification) {
        existingNotification.remove();
    }
    
    // Create new notification
    const notification = document.createElement('div');
    notification.id = 'copyNotification';
    notification.className = `copy-notification ${type}`;
    
    const icon = type === 'success' ? 'mdi-check-circle' : 'mdi-alert-circle';
    notification.innerHTML = `
        <i class="mdi ${icon} icon"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(notification);
    
    // Show notification
    setTimeout(() => {
        notification.classList.add('show');
    }, 100);
    
    // Hide notification after 3 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 400);
    }, 3000);
}

// Accordion functionality
function initApiAccordions() {
    const accordions = document.querySelectorAll('.api-accordion');
    
    accordions.forEach(accordion => {
        const header = accordion.querySelector('.api-accordion-header');
        const content = accordion.querySelector('.api-accordion-content');
        
        if (header && content) {
            header.addEventListener('click', function() {
                const isActive = accordion.classList.contains('active');
                
                // Close all other accordions
                accordions.forEach(otherAccordion => {
                    if (otherAccordion !== accordion) {
                        otherAccordion.classList.remove('active');
                    }
                });
                
                // Toggle current accordion
                accordion.classList.toggle('active');
                
                // Smooth scroll to accordion if opening
                if (!isActive) {
                    setTimeout(() => {
                        accordion.scrollIntoView({ 
                            behavior: 'smooth', 
                            block: 'start',
                            inline: 'nearest' 
                        });
                    }, 200);
                }
            });
        }
    });
    
    // Open first accordion by default
    if (accordions.length > 0) {
        accordions[0].classList.add('active');
    }
}

// Enhanced copy function with better error handling
function copyToClipboardEnhanced(text, button) {
    if (!text || typeof text !== 'string') {
        console.error('Invalid text to copy:', text);
        showMasterpieceNotification('Erreur: texte invalide', 'error');
        return;
    }

    // Clean the text
    const cleanText = text.trim();
    
    // Try modern clipboard API first
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(cleanText).then(() => {
            handleCopySuccess(button);
        }).catch(err => {
            console.warn('Clipboard API failed, trying fallback:', err);
            fallbackCopyToClipboard(cleanText, button);
        });
    } else {
        // Fallback for older browsers or non-secure contexts
        fallbackCopyToClipboard(cleanText, button);
    }
}

// Fallback copy method
function fallbackCopyToClipboard(text, button) {
    try {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);
        
        if (successful) {
            handleCopySuccess(button);
        } else {
            throw new Error('execCommand failed');
        }
    } catch (err) {
        console.error('All copy methods failed:', err);
        showMasterpieceNotification('Copie impossible sur ce navigateur', 'error');
    }
}

// Handle successful copy
function handleCopySuccess(button) {
    showMasterpieceNotification('✨ Copié avec succès !', 'success');
    
    if (button) {
        // Visual feedback on button
        button.classList.add('copied');
        const span = button.querySelector('span');
        const icon = button.querySelector('i');
        const originalText = span ? span.textContent : '';
        
        if (span) span.textContent = 'Copié !';
        if (icon) {
            icon.className = 'mdi mdi-check';
        }
        
        setTimeout(() => {
            button.classList.remove('copied');
            if (span) span.textContent = originalText || 'Copier';
            if (icon) {
                icon.className = 'mdi mdi-content-copy';
            }
        }, 2500);
    }
    
    console.log('Successfully copied to clipboard');
}

// Enhanced notification system
function showMasterpieceNotification(message, type = 'success') {
    // Remove existing notifications
    const existingNotifications = document.querySelectorAll('.masterpiece-notification');
    existingNotifications.forEach(notification => notification.remove());
    
    // Create new notification
    const notification = document.createElement('div');
    notification.className = `masterpiece-notification ${type}`;
    
    const iconClass = type === 'success' ? 'mdi-check-circle' : 'mdi-alert-circle';
    notification.innerHTML = `
        <i class="mdi ${iconClass} icon"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(notification);
    
    // Show with animation
    setTimeout(() => notification.classList.add('show'), 100);
    
    // Hide after delay
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 500);
    }, 3500);
}

// Updated global copy function
function copyToClipboard(text) {
    copyToClipboardEnhanced(text, event?.target?.closest('.masterpiece-copy-btn, .api-copy-btn'));
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 API Documentation JavaScript loaded');
    
    // Initialize accordions
    initApiAccordions();
    
    // Add enhanced hover effects to code blocks
    const codeBlocks = document.querySelectorAll('.masterpiece-code-block, .api-code-block');
    codeBlocks.forEach(block => {
        block.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
        });
        
        block.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
    
    // Add click handlers for all copy buttons
    const copyButtons = document.querySelectorAll('.masterpiece-copy-btn, .api-copy-btn');
    copyButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
        });
    });
    
    // Add keyboard navigation for accordions
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' || e.key === ' ') {
            const target = e.target.closest('.api-accordion-header');
            if (target) {
                e.preventDefault();
                target.click();
            }
        }
    });
    
    console.log('✅ All API documentation features initialized');
});

// Utility function to format code for copying
function formatCodeForCopy(code) {
    return code.trim().replace(/\n\s+/g, '\n');
}

// Export functions for global use
window.copyToClipboard = copyToClipboard;
window.showCopyNotification = showCopyNotification;