class TelegramMonitor extends React.Component {
  static buildProps() {
    return {
      key: 'TelegramMonitor',
    };
  }

  constructor(props) {
    super(props);
    this.state = {
      messages: null,
    };
    this.fetchMessages = this.fetchMessages.bind(this);
  }

  async componentDidMount() {
    this.fetchMessages();
  }

  on_app_became_visible() {
    this.fetchMessages();
  }

  fetchMessages() {
    mJsonGet('/messages', (res) => {
      this.setState({ messages: res });
    });
  }

  formatTimestamp(isoString) {
    const date = new Date(isoString);
    return date.toLocaleString();
  }

  render() {
    if (!this.state.messages) {
      return ( <div className="app-loading">Loading...</div> );
    }

    return (
      <div id="TelegramMonitorContainer">
        <h3>
          <img src="/favicon.ico" alt="Telgram service" />
          Telegram Messages History
        </h3>
        {this.state.messages.length === 0 ? (
          <p>No messages yet</p>
        ) : (
          <ul>
            {this.state.messages.map((msg, idx) => this.renderMessage(msg, idx))}
          </ul>
        )}
      </div>
    )
  }

  renderMessage(msg, idx) {
    const directionStyle = msg.direction === 'sent'
      ? { color: '#4a90e2', fontWeight: 'bold' }
      : { color: '#50c878', fontWeight: 'bold' };

    let messageContent = '';
    let chatId = '';

    if (typeof msg.message === 'string') {
      const parts = msg.message.split(', ');
      chatId = parts[0];

      if (parts.length === 2) {
        messageContent = parts[1];
      } else if (parts.length === 3) {
        const path = parts[1];
        const caption = parts[2];
        messageContent = `📷 Photo: ${path}${caption ? ` (${caption})` : ''}`;
      } else {
        messageContent = msg.message;
      }
    } else {
      if (msg.direction === 'sent') {
        if (msg.message.type === 'text') {
          messageContent = msg.message.text;
        } else if (msg.message.type === 'photo') {
          messageContent = `📷 Photo: ${msg.message.path}`;
          if (msg.message.caption) {
            messageContent += ` (${msg.message.caption})`;
          }
        }
      } else {
        if (msg.message.text) {
          messageContent = msg.message.text;
        } else if (msg.message.cmd) {
          messageContent = `/${msg.message.cmd}`;
          if (msg.message.cmd_args && msg.message.cmd_args.length > 0) {
            messageContent += ' ' + msg.message.cmd_args.join(' ');
          }
        } else {
          messageContent = JSON.stringify(msg.message);
        }
      }
    }

    const fromInfo = msg.direction === 'received' && typeof msg.message === 'object' && msg.message.from
      ? ` from ${msg.message.from.first_name || msg.message.from.username || msg.message.from.id}`
      : (chatId ? ` to ${chatId}` : '');

    return (
      <li key={idx}>
        <div style={{ marginBottom: '5px' }}>
          <span style={directionStyle}>
            {msg.direction === 'sent' ? '→ Sent' : '← Received'}
          </span>
          <span style={{ color: '#888', fontSize: '0.9em', marginLeft: '10px' }}>
            {this.formatTimestamp(msg.timestamp)}
          </span>
          <span style={{ fontSize: '0.9em' }}>
            {fromInfo}
          </span>
        </div>
        <div style={{ marginLeft: '20px', fontSize: '0.95em' }}>
          {messageContent}
        </div>
      </li>
    );
  }
}
