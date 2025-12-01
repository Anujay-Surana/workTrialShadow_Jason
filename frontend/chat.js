const API_BASE_URL = 'http://localhost:8080';

let chatHistory = [];
let isStreaming = false;

// Check authentication status on page load
async function checkAuthStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/status`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (data.authenticated && data.user) {
            // Check if initialization is complete
            if (data.status === 'active') {
                showChatUI(data.user);
            } else {
                // Redirect back to main page for initialization
                window.location.href = '/index.html';
            }
        } else {
            // Not authenticated, redirect to main page
            window.location.href = '/index.html';
        }
    } catch (error) {
        console.error('Error checking auth status:', error);
        window.location.href = '/index.html';
    }
}

// Show chat UI with user info
function showChatUI(user) {
    document.getElementById('userName').textContent = user.name || 'User';
    document.getElementById('userEmail').textContent = user.email || '';
    document.getElementById('avatar-img').src = user.picture || 'user.png';
}

// Handle Sign Out button click
async function handleSignOut() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/logout`, {
            method: 'POST',
            credentials: 'include'
        });
        
        if (response.ok) {
            // Redirect to main page
            window.location.href = '/index.html';
        } else {
            console.error('Logout failed');
            // Still redirect even if logout request failed
            window.location.href = '/index.html';
        }
    } catch (error) {
        console.error('Error during logout:', error);
        // Still redirect even if logout request failed
        window.location.href = '/index.html';
    }
}

// Add message to chat
function addMessage(role, content, references = null) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message message-${role}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Render markdown
    contentDiv.innerHTML = marked.parse(content);
    
    messageDiv.appendChild(contentDiv);
    
    // Add references if provided
    if (references && references.length > 0) {
        const referencesDiv = document.createElement('div');
        referencesDiv.className = 'references';
        
        const titleDiv = document.createElement('div');
        titleDiv.className = 'references-title';
        titleDiv.textContent = 'References:';
        referencesDiv.appendChild(titleDiv);
        
        references.forEach(ref => {
            const refItem = document.createElement('div');
            refItem.className = 'reference-item';
            
            let refText = '';
            if (ref.type === 'email') {
                refText = `[Email] ${ref.title} (from ${ref.from}, ${ref.date})`;
            } else if (ref.type === 'schedule') {
                refText = `[Calendar] ${ref.title} (${ref.start_time}, ${ref.location})`;
            } else if (ref.type === 'file') {
                refText = `[File] ${ref.title} (${ref.path})`;
            } else if (ref.type === 'attachment') {
                let attachmentText = `[Attachment] ${ref.title}`;
                if (ref.subject) {
                    attachmentText += ` from email: "${ref.subject}"`;
                }
                if (ref.from) {
                    attachmentText += ` (from ${ref.from}`;
                    if (ref.date) {
                        attachmentText += `, ${ref.date}`;
                    }
                    attachmentText += ')';
                }
                refText = attachmentText;
            }
            
            refItem.innerHTML = `<span class="reference-type">${ref.type}</span>: ${refText}`;
            referencesDiv.appendChild(refItem);
        });
        
        messageDiv.appendChild(referencesDiv);
    }
    
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    return messageDiv;
}

// Create typing indicator
function createTypingIndicator() {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-assistant';
    messageDiv.id = 'typing-indicator';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content typing-indicator';
    contentDiv.textContent = 'Thinking...';
    
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    return messageDiv;
}

// Remove typing indicator
function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

// Send message
async function sendMessage() {
    if (isStreaming) return;
    
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Clear input
    input.value = '';
    
    // Add user message to chat
    addMessage('user', message);
    chatHistory.push({ role: 'user', content: message });
    
    // Disable input while streaming
    isStreaming = true;
    input.disabled = true;
    document.getElementById('sendBtn').disabled = true;
    
    // Show typing indicator
    const typingIndicator = createTypingIndicator();
    
    try {
        // Call chat API
        const response = await fetch(`${API_BASE_URL}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({
                message: message,
                history: chatHistory.slice(-10) // Send last 10 messages
            })
        });
        
        if (!response.ok) {
            throw new Error('Chat request failed');
        }
        
        // Remove typing indicator
        removeTypingIndicator();
        
        // Create message div for streaming response
        const messagesContainer = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message message-assistant';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        messageDiv.appendChild(contentDiv);
        messagesContainer.appendChild(messageDiv);
        
        // Stream response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let accumulatedContent = '';
        let references = [];
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const jsonStr = line.slice(6).trim();
                        if (!jsonStr) continue;
                        
                        const data = JSON.parse(jsonStr);
                        
                        if (data.type === 'content') {
                            accumulatedContent += data.content;
                            // Update rendered markdown in real-time
                            contentDiv.innerHTML = marked.parse(accumulatedContent);
                            messagesContainer.scrollTop = messagesContainer.scrollHeight;
                        } else if (data.type === 'references') {
                            references = data.references;
                        } else if (data.type === 'done') {
                            // Add references if any
                            if (references.length > 0) {
                                const referencesDiv = document.createElement('div');
                                referencesDiv.className = 'references';
                                
                                const titleDiv = document.createElement('div');
                                titleDiv.className = 'references-title';
                                titleDiv.textContent = 'References:';
                                referencesDiv.appendChild(titleDiv);
                                
                                references.forEach(ref => {
                                    const refItem = document.createElement('div');
                                    refItem.className = 'reference-item';
                                    
                                    let refText = '';
                                    if (ref.type === 'email') {
                                        refText = `${ref.title} (from ${ref.from}, ${ref.date})`;
                                    } else if (ref.type === 'schedule') {
                                        refText = `${ref.title} (${ref.start_time}, ${ref.location})`;
                                    } else if (ref.type === 'file') {
                                        refText = `${ref.title} (${ref.path})`;
                                    } else if (ref.type === 'attachment') {
                                        refText = `${ref.title}`;
                                        if (ref.subject) {
                                            refText += ` from email: "${ref.subject}"`;
                                        }
                                        if (ref.from) {
                                            refText += ` (from ${ref.from}`;
                                            if (ref.date) {
                                                refText += `, ${ref.date}`;
                                            }
                                            refText += ')';
                                        }
                                    }
                                    
                                    refItem.innerHTML = `<span class="reference-type">[${ref.type}]</span> ${refText}`;
                                    referencesDiv.appendChild(refItem);
                                });
                                
                                messageDiv.appendChild(referencesDiv);
                            }
                            
                            // Add to history
                            chatHistory.push({ role: 'assistant', content: accumulatedContent });
                        } else if (data.type === 'error') {
                            console.error('Chat error:', data.error);
                            contentDiv.textContent = 'Sorry, an error occurred. Please try again.';
                        }
                    } catch (parseError) {
                        console.error('Error parsing SSE data:', parseError, 'Line:', line);
                    }
                }
            }
        }
        
    } catch (error) {
        console.error('Error during chat:', error);
        removeTypingIndicator();
        addMessage('assistant', 'Sorry, an error occurred. Please try again.');
    } finally {
        // Re-enable input
        isStreaming = false;
        input.disabled = false;
        document.getElementById('sendBtn').disabled = false;
        input.focus();
    }
}

// Handle Enter key in input
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Configure marked options
    marked.setOptions({
        breaks: true,
        gfm: true
    });
    
    // Set up Sign Out button
    document.getElementById('signOutBtn').addEventListener('click', handleSignOut);
    
    // Set up Send button
    document.getElementById('sendBtn').addEventListener('click', sendMessage);
    
    // Set up Enter key handler
    document.getElementById('chatInput').addEventListener('keypress', handleKeyPress);
    
    // Check auth status
    checkAuthStatus();
});
