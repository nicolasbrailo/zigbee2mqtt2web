class ScenesPane extends React.Component {
  constructor(props) {
    super(props);
  }

  requestScene(name) {
    console.log(`Requesting scene ${name}`)
    this.props.thing_registry.set_thing(this.props.scenes.name, name)
  }

  render() {
    if (!this.props.scenes) return '';
    let scenes = [];
    for (const scene_name of Object.keys(this.props.scenes.actions)) {
      scenes.push(
        <li key={`scene_${scene_name}`}>
          <button key="button_set_scene_{$scene_name}"
             onClick={ () => this.requestScene(scene_name) }>
            {scene_name}
          </button>
        </li>
      );
    }

    return <div id="scenes" className="card" key="scenes_list">
            <ul>{scenes}</ul>
           </div>;
  }
}
