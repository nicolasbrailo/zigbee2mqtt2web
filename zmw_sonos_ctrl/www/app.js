class FixMySpeakersMonitor extends React.Component {
  static buildProps() {
    return {
      key: 'FixMySpeakersMonitor',
    };
  }

  constructor(props) {
    super(props);
    this.state = {
      messages: [],
      running: false,
    };
  }

  startTest = () => {
    if (this.ws) {
      this.ws.close();
    }
    this.setState({ messages: [], running: true }, () => {
      this.connectWebSocket();
    });
  };

  connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws_test`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      console.log('WebSocket message received:', event.data);
      this.setState(prev => ({
        messages: [...prev.messages, event.data]
      }));
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.setState(prev => ({
        messages: [...prev.messages, `Error: ${error.message || 'Connection error'}`],
        running: false,
      }));
    };

    ws.onclose = () => {
      console.log('WebSocket closed');
      this.setState({ running: false });
    };

    this.ws = ws;
  }

  on_app_became_visible() {
    // No action on refresh
  }

  render() {
    const { messages, running } = this.state;
    return React.createElement('div', null,
      React.createElement('button',
        { onClick: this.startTest, disabled: running },
        running ? 'Running...' : 'Start Test'
      ),
      React.createElement('ul', null,
        messages.map((msg, idx) =>
          React.createElement('li', { key: idx }, msg)
        )
      )
    );
  }
}

z2mStartReactApp('#app_root', FixMySpeakersMonitor);
