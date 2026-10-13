// Moves a (kinematic) model back and forth between two points at constant speed.
// Optionally waits until a trigger model comes within trigger_distance (horizontal) of
// trigger_point (or of the travel segment if no point is given), so the crossing happens
// when the vehicle approaches.
//
// <plugin name="cart" filename="libctrack_moving_obstacle.so">
//   <model>RCCart_C</model>
//   <start>39 -33 0</start> <end>39 -18.5 0</end>   world ENU [m]
//   <speed>1.0</speed>                              [m/s]
//   <loop>true</loop>                               ping-pong (false: stop at end)
//   <trigger_model>x8</trigger_model>               optional
//   <trigger_distance>15</trigger_distance>         [m]
//   <trigger_point>39 -26 0</trigger_point>         optional, world ENU [m]
// </plugin>
#include <iostream>

#include <gazebo/common/Events.hh>
#include <gazebo/common/Plugin.hh>
#include <gazebo/physics/physics.hh>
#include <ignition/math/Pose3.hh>

#include <cmath>

namespace gazebo
{
class MovingObstaclePlugin : public WorldPlugin
{
public:
  void Load(physics::WorldPtr world, sdf::ElementPtr sdf) override
  {
    world_ = world;
    name_ = sdf->GetAttribute("name")->GetAsString();
    model_name_ = sdf->Get<std::string>("model");
    start_ = sdf->Get<ignition::math::Vector3d>("start");
    end_ = sdf->Get<ignition::math::Vector3d>("end");
    speed_ = sdf->Get<double>("speed", 1.0).first;
    loop_ = sdf->Get<bool>("loop", true).first;
    trigger_model_ = sdf->Get<std::string>("trigger_model", "").first;
    trigger_distance_ = sdf->Get<double>("trigger_distance", 0.0).first;
    has_trigger_point_ = sdf->HasElement("trigger_point");
    if (has_trigger_point_)
      trigger_point_ = sdf->Get<ignition::math::Vector3d>("trigger_point");
    length_ = (end_ - start_).Length();
    update_ = event::Events::ConnectWorldUpdateBegin(std::bind(&MovingObstaclePlugin::OnUpdate, this));
    gzmsg << "[" << name_ << "] " << model_name_ << " " << start_ << " -> " << end_ << " at " << speed_
          << " m/s" << (trigger_model_.empty() ? "" : ", triggered by " + trigger_model_) << std::endl;
  }

private:
  bool Triggered()
  {
    if (trigger_model_.empty())
      return true;
    physics::ModelPtr trig = world_->ModelByName(trigger_model_);
    if (!trig)
      return false;
    ignition::math::Vector3d p = trig->WorldPose().Pos(), a = start_, b = end_;
    p.Z(0); a.Z(0); b.Z(0);
    if (has_trigger_point_) {
      ignition::math::Vector3d q = trigger_point_;
      q.Z(0);
      return (p - q).Length() <= trigger_distance_;
    }
    // horizontal distance from the trigger model to the travel segment
    const ignition::math::Vector3d ab = b - a;
    const double t = ab.SquaredLength() > 0 ? std::clamp((p - a).Dot(ab) / ab.SquaredLength(), 0.0, 1.0) : 0.0;
    return (p - (a + t * ab)).Length() <= trigger_distance_;
  }

  void OnUpdate()
  {
    if (!model_) {
      model_ = world_->ModelByName(model_name_);
      if (!model_)
        return;
    }
    const double now = world_->SimTime().Double();
    if (t0_ < 0) {
      if (!Triggered()) {
        model_->SetWorldPose(ignition::math::Pose3d(start_, ignition::math::Quaterniond::Identity));
        return;
      }
      t0_ = now;
      gzmsg << "[" << name_ << "] started at t=" << now << " s" << std::endl;
      std::cout.flush();  // gzserver stdout is usually a log file
    }
    double s = speed_ * (now - t0_);
    if (loop_ && length_ > 0) {
      s = std::fmod(s, 2 * length_);
      if (s > length_)
        s = 2 * length_ - s;
    } else {
      s = std::min(s, length_);
    }
    const ignition::math::Vector3d pos = length_ > 0 ? start_ + (end_ - start_) * (s / length_) : start_;
    model_->SetWorldPose(ignition::math::Pose3d(pos, ignition::math::Quaterniond::Identity));
  }

  physics::WorldPtr world_;
  physics::ModelPtr model_;
  event::ConnectionPtr update_;
  std::string name_, model_name_, trigger_model_;
  ignition::math::Vector3d start_, end_, trigger_point_;
  double speed_{1.0}, trigger_distance_{0.0}, length_{0.0}, t0_{-1.0};
  bool loop_{true}, has_trigger_point_{false};
};
GZ_REGISTER_WORLD_PLUGIN(MovingObstaclePlugin)
}  // namespace gazebo
