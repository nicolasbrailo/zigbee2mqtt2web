class DebouncedRange extends React.Component {
  constructor(props) {
    super(props);

    // Fail early on missing props
    props.min.this_is_a_required_prop;
    props.max.this_is_a_required_prop;
    props.value.this_is_a_required_prop;

    const val = (props.value)? props.value : props.min;
    this.state = {
      changing: false,
      value: val,
    };
  }

  UNSAFE_componentWillReceiveProps(next_props) {
    // Without this, we need to rely on having a key being set for the
    // component to update its state from both parent and internal changes
    // If UNSAFE_componentWillReceiveProps stops working (it may be removed?)
    // then using this element will need to include a key with the current
    // value., Eg:
    // <DebouncedRange
    //       key={`${UNIQ_ELEMENT_NAME}_slider_${parent.state.value}`}
    //       min={$min}
    //       max={$max}
    //       value={parent.state.value} />
    const val = (next_props && next_props.value)? next_props.value : 0;
    this.setState({value: val});
  }

  onChange(value) {
      this.setState({value: value});
  }

  onMouseUp(_) {
      this.setState({changing: false});
      this.props.onChange({target: { value: this.state.value }});
  }

  onMouseDown(_) {
      this.setState({changing: true});
  }

  render() {
    return <input type="range"
             onChange={ (evnt) => this.onChange(evnt.target.value)}
             onMouseUp={ (evnt) => { this.onMouseUp(evnt.target.value) }  }
             onMouseDown={ (evnt) => this.onMouseDown(evnt.target.value) }
             onTouchStart={ (evnt) => this.onMouseDown(evnt.target.value)}
             onTouchEnd={ (evnt) => this.onMouseUp(evnt.target.value)}
             className={this.props.className}
             min={this.props.min}
             max={this.props.max}
             value={this.state.value} />
  }
}
