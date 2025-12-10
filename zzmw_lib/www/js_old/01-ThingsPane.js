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

  _getOrderedThings(props) {
    // Create default order for list
    let default_things_order = [];
    for (const elm of props.things) {
      default_things_order.push(elm.props.name);
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

    if (order_changed) {
      this.props.local_storage.save('ThingsPane.things_order', cached_things_order);
    }

    return cached_things_order;
  }

  constructor(props) {
    super(props);

    this.props.onReorderThings.toggle = () => {
      this.setState({reordering: !this.state.reordering});
    };

    this.props.showHiddenThings.toggle = () => {
      this.setState({showHiddenThings: !this.state.showHiddenThings});
    };

    const things_lookup = {};
    for (const elm of props.things) {
      things_lookup[elm.props.name] = elm;
    }

    this.state = {
      things_lookup: things_lookup,
      things_order: this._getOrderedThings(props),
      reordering: false,
      showHiddenThings: false,
      visibleGroup: null,
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
    return <div key="global_thing_list_pane">
             {this._buildList()}
           </div>
  }

  _buildList() {
    const groupedThingList = new Map();
    groupedThingList.set(null, []);
    let current_group = null;
    for (const thing_name of this.state.things_order) {
      const thing = this.state.things_lookup[thing_name];

      let group = null;
      if (thing.props.user_defined) group = thing.props.user_defined.ui_group;
      if (group === undefined) group = null;
      if (group != current_group) {
        current_group = group;
        if (!groupedThingList.has(current_group)) {
          groupedThingList.set(current_group, []);
        }
      }

      const ui_hide = thing.props.user_defined && thing.props.user_defined.ui_hide;
      const classNames = (!this.state.showHiddenThings && ui_hide)? 'is-hidden' : '';
      groupedThingList.get(current_group).push(
        <li className={classNames} key={`${thing.props.name}_thing_li`}>
          {thing}
        </li>)
    }

    const groupList = [];
    const visibleGroup = (() => {
      if (this.state.visibleGroup) return this.state.visibleGroup;
      const groups = Array.from(groupedThingList.entries());
      if (groups.length == 0) return null;
      return groups[0][0];
    })();

    for (const e of groupedThingList.entries()) {
      const group = e[0];
      if (!group) continue; // We'll add null-group at the bottom

      const thinglist = e[1];
      const visible = (!this.state.showHiddenThings && group != null && group != visibleGroup)? 'is-hidden' : '';
      const expandGroupCtrl = (
        <div onClick={_ => this.setState({visibleGroup: group})} className="is-full-width text-dark bd-primary is-small is-a-bit-rounded">
          <b>{group}</b>
        </div>)
      groupList.push(
        <div className="card" key={`${group}_thing_pane_group`}>
        {expandGroupCtrl}
        <ul className={visible} key={`${group}_thing_pane_group_ul`}>
          {thinglist}
        </ul>
        </div>);
    }

    if (groupedThingList.get(null).length > 0) {
      groupList.push(
        <div className="card" key={`nullgroup_thing_pane_group`}>
        <ul key={`nullgroup_thing_pane_group_ul`}>
          {groupedThingList.get(null)}
        </ul>
        </div>);
    }

    return groupList;
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
