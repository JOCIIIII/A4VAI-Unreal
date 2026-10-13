// Localized wind (e.g. a fan bank) for Gazebo Classic.
// While the vehicle link is inside an axis-aligned box, applies aerodynamic drag toward the
// wind: F = 0.5 * rho * CdA * |v_rel| * v_rel, v_rel = wind - link velocity (world frame).
// Works with any vehicle model: no change to the model SDF, motor-model wind stays untouched.
//
// <plugin name="wind_b" filename="libctrack_wind_zone.so">
//   <model>x8</model>              vehicle model (spawned later is fine)
//   <link></link>                  optional, default canonical link
//   <min>69 -23 0</min> <max>89 -3 10</max>   zone box, world ENU [m]
//   <velocity>-3 0 0</velocity>    wind, world ENU [m/s]
//   <cd_area>0.1</cd_area>         drag coefficient x reference area [m^2]
//   <air_density>1.225</air_density>
// </plugin>
#include <iostream>

#include <gazebo/common/Events.hh>
#include <gazebo/common/Plugin.hh>
#include <gazebo/physics/physics.hh>
#include <ignition/math/Vector3.hh>

namespace gazebo
{
class WindZonePlugin : public WorldPlugin
{
public:
  void Load(physics::WorldPtr world, sdf::ElementPtr sdf) override
  {
    world_ = world;
    name_ = sdf->GetAttribute("name")->GetAsString();
    model_name_ = sdf->Get<std::string>("model", "x8").first;
    link_name_ = sdf->Get<std::string>("link", "").first;
    min_ = sdf->Get<ignition::math::Vector3d>("min");
    max_ = sdf->Get<ignition::math::Vector3d>("max");
    wind_ = sdf->Get<ignition::math::Vector3d>("velocity");
    cd_area_ = sdf->Get<double>("cd_area", 0.1).first;
    rho_ = sdf->Get<double>("air_density", 1.225).first;
    update_ = event::Events::ConnectWorldUpdateBegin(std::bind(&WindZonePlugin::OnUpdate, this));
    gzmsg << "[" << name_ << "] wind " << wind_ << " m/s in box " << min_ << " .. " << max_
          << " on model '" << model_name_ << "', CdA " << cd_area_ << std::endl;
  }

private:
  void OnUpdate()
  {
    if (!link_) {
      physics::ModelPtr model = world_->ModelByName(model_name_);
      if (!model)
        return;
      link_ = link_name_.empty() ? model->GetLink() : model->GetLink(link_name_);
      if (!link_)
        return;
    }
    const ignition::math::Vector3d p = link_->WorldPose().Pos();
    const bool inside = p.X() >= min_.X() && p.X() <= max_.X() && p.Y() >= min_.Y() && p.Y() <= max_.Y() &&
                        p.Z() >= min_.Z() && p.Z() <= max_.Z();
    if (inside != inside_) {
      inside_ = inside;
      gzmsg << "[" << name_ << "] vehicle " << (inside ? "entered" : "left") << " wind zone at t="
            << world_->SimTime().Double() << " s" << std::endl;
      std::cout.flush();  // gzserver stdout is usually a log file
    }
    if (!inside)
      return;
    const ignition::math::Vector3d v_rel = wind_ - link_->WorldLinearVel();
    link_->AddForce(0.5 * rho_ * cd_area_ * v_rel.Length() * v_rel);
  }

  physics::WorldPtr world_;
  physics::LinkPtr link_;
  event::ConnectionPtr update_;
  std::string name_, model_name_, link_name_;
  ignition::math::Vector3d min_, max_, wind_;
  double cd_area_{0.1}, rho_{1.225};
  bool inside_{false};
};
GZ_REGISTER_WORLD_PLUGIN(WindZonePlugin)
}  // namespace gazebo
