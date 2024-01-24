class ThingsPane extends React.Component {
  static buildProps(local_storage, things) {
    // Expose state through props... surely that's the intended purpose, right?
    const cbObjReorderThings = {
      toggle: null,
    };

    const cbShowHiddenThings = {
      toggle: null,
    }

    return {
      key: 'global_thing_list',
      things: things,
      local_storage: local_storage,
      onReorderThings: cbObjReorderThings,
      showHiddenThings: cbShowHiddenThings,
    };
  }

  constructor(props) {
    super(props);

    // Create default order for list
    let default_things_order = [];
    let things_lookup = {};
    for (const elm of props.things) {
      default_things_order.push(elm.props.name);
      things_lookup[elm.props.name] = elm;
    }

    // Try to fetch from cache
    let cached_things_order = this.props.local_storage.get('ThingsPane.things_order', default_things_order);
    const set_existing_things = new Set(default_things_order);
    const set_cached_things_order = new Set(cached_things_order);
    let order_changed = false;

    // If non existing things are in the order, delete them
    for (const [idx,elm] of cached_things_order.entries()) {
      if (!set_existing_things.has(elm)) {
        delete cached_things_order[idx];
        order_changed = true;
      }
    }
    cached_things_order = cached_things_order.filter(x => x != null);

    // If things are missing from the order, add them to the end
    for (const elm of default_things_order) {
      if (!set_cached_things_order.has(elm)) {
        cached_things_order.push(elm);
        order_changed = true;
      }
    }

    this.props.onReorderThings.toggle = () => {
      this.setState({reordering: !this.state.reordering});
    };

    this.props.showHiddenThings.toggle = () => {
      this.setState({showHiddenThings: !this.state.showHiddenThings});
    };

    if (order_changed) {
      this.props.local_storage.save('ThingsPane.things_order', cached_things_order);
    }

    this.state = {
      things_lookup: things_lookup,
      things_order: cached_things_order,
      reordering: false,
      showHiddenThings: false,
    };
  }

  reorder(idx, delta) {
    if ((idx + delta < 0) || (idx + delta >= this.state.things_order.length)) {
      return;
    }
    let new_order = this.state.things_order;
    const tmp = new_order[idx];
    new_order[idx] = new_order[idx+delta];
    new_order[idx+delta] = tmp;

    this.props.local_storage.save('ThingsPane.things_order', new_order);
    this.setState({things_order: new_order});
  }

  render() {
    if (this.state.reordering) return this.render_reordering();

    const thing_list = this.state.things_order.map((thing_name, idx) => {
      const thing = this.state.things_lookup[thing_name];
      const classNames = (!this.state.showHiddenThings && thing.props.start_hidden)? 'is-hidden' : '';
      return <li className={classNames} key={`${thing.props.name}_thing_li`}>
              {thing}
            </li>
    });
    return <ul key="global_thing_list_pane">
             {thing_list}
           </ul>
  }

  render_reordering() {
    const thing_list = this.state.things_order.map((thing_name, idx) => {
      const thing = this.state.things_lookup[thing_name];
      const reorder_up = () => {
        return (idx == 0)?
                  '▲' :
                  <a className="thing-list-reorder-link" onClick={evnt => this.reorder(idx, -1)}>▲</a>
      }
      const reorder_down = () => {
        return (idx == this.state.things_order.length-1)?
                  '▼' :
                  <a className="thing-list-reorder-link" onClick={evnt => this.reorder(idx, +1)}>▼</a>
      }
      return <li key={`${thing.props.name}_thing_reorder_li`}>
        <div className="thing_div row"
             key={`${thing.props.name}_reorder_div`}>
          <div className="col-primary-action">
            { reorder_down() }
            { reorder_up() }
          </div>
          <div className="col-fixed-fill">
            <h3>{thing.props.name}</h3>
          </div>
        </div>
      </li>
    });

    return <ul key="global_thing_list_pane">
             {thing_list}
           </ul>
  }
}
